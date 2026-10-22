import * as THREE from "three";
import { ObjectState, type ZoneLayout } from "@/data/types";
import { Clock } from "@/core/Clock";
import { InputManager } from "@/core/InputManager";
import { AssetLoader } from "@/core/AssetLoader";
import { SceneManager } from "@/core/SceneManager";
import { PlayerController } from "@/systems/PlayerController";
import { FlashlightSystem } from "@/systems/FlashlightSystem";
import { StaminaSystem } from "@/systems/StaminaSystem";
import { InteractionSystem } from "@/systems/InteractionSystem";
import { ObjectStateMachine } from "@/systems/ObjectStateMachine";
import { ShiftManager, type ShiftEndReason } from "@/systems/ShiftManager";
import { getShiftConfig, ZOMBIE_APPEARS_AT_SHIFT } from "@/systems/DifficultyScaler";
import { HintSystem } from "@/systems/HintSystem";
import { HealthSystem } from "@/systems/HealthSystem";
import { ZombieSystem } from "@/systems/ZombieSystem";
import { SaveSystem, type SaveData } from "@/systems/SaveSystem";
import { SkillSystem, SKILLS, type SkillId } from "@/systems/SkillSystem";
import { WalletSystem, TASK_REWARD, shiftCompletionBonus } from "@/systems/WalletSystem";
import { trackEvent } from "@/sdk/Analytics";
import { showFullscreenAd } from "@/sdk/Ads";
import { HUD, type HUDTask } from "@/ui/HUD";
import { formatTaskLabel } from "@/ui/taskLabels";
import { ShiftReportScreen } from "@/ui/ShiftReportScreen";
import { PauseMenu } from "@/ui/PauseMenu";
import { ShopScreen, type ShopState } from "@/ui/ShopScreen";
import { createPostProcessing, type PostProcessingPipeline } from "@/render/PostProcessing";

const SPRINT_SPEED_MULTIPLIER = 1.6;
// На каком расстоянии (по горизонтали) от двери дома смотрителя E открывает магазин.
const SHOP_RADIUS = 2.8;
// Пока открыт магазин, камера смотрит от двери на кладбище (фон как на референсе),
// почти горизонтально — за панелями видны деревья, фонарь и небо. При закрытии возвращается прежний взгляд.
const SHOP_VIEW_PITCH = 0.02;

export class Game {
  private readonly renderer: THREE.WebGLRenderer;
  private readonly camera: THREE.PerspectiveCamera;
  private readonly clock = new Clock();
  private readonly input = new InputManager();
  private readonly assetLoader = new AssetLoader();
  private readonly stateMachine = new ObjectStateMachine();
  readonly sceneManager = new SceneManager(this.assetLoader, this.stateMachine);

  private readonly playerController: PlayerController;
  readonly flashlight = new FlashlightSystem();
  private readonly stamina = new StaminaSystem();
  private readonly interaction: InteractionSystem;
  private readonly health = new HealthSystem();
  private readonly zombie: ZombieSystem;
  readonly shiftManager: ShiftManager;
  readonly hintSystem: HintSystem;
  private readonly saveSystem = new SaveSystem();
  private readonly skills = new SkillSystem();
  private readonly wallet = new WalletSystem();
  /** Записи сохранения идут строго по очереди: каждая читает текущее сохранение и
   *  дописывает своё поле — параллельно они затирали бы друг друга. */
  private saveQueue: Promise<void> = Promise.resolve();

  private readonly hud: HUD;
  private readonly shiftReportScreen: ShiftReportScreen;
  private readonly pauseMenu: PauseMenu;
  private readonly shopScreen: ShopScreen;
  private readonly postProcessing: PostProcessingPipeline;

  private running = false;
  private currentShiftIndex = 1;
  private coinsThisShift = 0;
  /** Дверь дома смотрителя (магазин) — ищется в зоне один раз, после загрузки. */
  private shopAnchor: { x: number; z: number } | null | undefined = undefined;
  private readonly lookBeforeShop = { yaw: 0, pitch: 0 };

  constructor(
    private readonly canvas: HTMLCanvasElement,
    uiRoot: HTMLElement,
  ) {
    this.renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
    this.renderer.shadowMap.enabled = true;
    this.renderer.shadowMap.type = THREE.PCFShadowMap;

    this.camera = new THREE.PerspectiveCamera(
      70,
      canvas.clientWidth / canvas.clientHeight,
      0.1,
      1000,
    );
    // Камера добавляется в сцену, чтобы прикреплённый к ней SpotLight (фонарик)
    // попадал в граф рендера — THREE обходит scene.children, а не камеру отдельно.
    this.sceneManager.scene.add(this.camera);
    this.postProcessing = createPostProcessing(this.renderer, this.sceneManager.scene, this.camera);

    this.playerController = new PlayerController(this.camera, this.input);
    this.zombie = new ZombieSystem(this.sceneManager);
    this.shiftManager = new ShiftManager(
      this.stateMachine,
      (reason) => this.onShiftEnd(reason),
      () => this.onTaskCompleted(),
    );
    this.interaction = new InteractionSystem(
      this.camera,
      this.stateMachine,
      this.shiftManager,
      this.sceneManager,
    );
    this.hintSystem = new HintSystem(this.sceneManager.scene);
    this.flashlight.attachToCamera(this.camera);

    this.hud = new HUD(uiRoot, () => this.openShop());
    this.shiftReportScreen = new ShiftReportScreen(uiRoot, () => {
      showFullscreenAd(undefined, () => this.startShift());
    });
    this.pauseMenu = new PauseMenu(
      uiRoot,
      this.saveSystem,
      () => this.togglePause(),
      () => window.location.reload(), // нет отдельного экрана главного меню — пока просто рестарт
    );
    this.shopScreen = new ShopScreen(
      uiRoot,
      (id) => this.buySkill(id),
      () => this.closeShop(),
    );

    void this.saveSystem.load().then((data) => {
      this.wallet.load(data.coins);
      this.skills.load(data.skills);
      this.applySkillEffects();
    });

    this.input.attach(canvas);
    window.addEventListener("resize", () => this.onResize());
    this.onResize();
  }

  /** Загружает зону и запускает первую смену в ней. */
  async beginFirstShift(layout: ZoneLayout): Promise<void> {
    await this.sceneManager.loadZone(layout);
    this.startShift();
  }

  start(): void {
    if (this.running) return;
    this.running = true;
    requestAnimationFrame(this.loop);
  }

  stop(): void {
    this.running = false;
  }

  private readonly loop = (nowMs: number): void => {
    if (!this.running) return;

    const delta = this.clock.tick(nowMs);
    this.update(delta);
    this.postProcessing.update(delta);
    this.postProcessing.render();

    requestAnimationFrame(this.loop);
  };

  private update(deltaSec: number): void {
    // Пока открыт экран итогов смены — Escape не должен открывать поверх него паузу,
    // там и так уже всё остановлено, а курсор специально отпущен под клик по кнопке.
    if (!this.shiftReportScreen.isVisible() && this.input.consumeKeyPress("Escape")) {
      if (this.shopScreen.isVisible()) this.closeShop();
      else this.togglePause();
    }

    const flashlightPressed = this.input.consumeKeyPress("KeyF");
    const interactPressed = this.input.consumeKeyPress("KeyE");
    const shopOpen = this.shopScreen.isVisible();
    if (shopOpen && interactPressed) this.closeShop();

    if (!this.pauseMenu.isVisible() && !shopOpen) {
      const wantsSprint = this.input.isKeyDown("ShiftLeft") || this.input.isKeyDown("ShiftRight");
      this.stamina.update(deltaSec, wantsSprint);
      const sprintMultiplier = this.stamina.isSprinting() ? SPRINT_SPEED_MULTIPLIER : 1;

      this.playerController.update(
        deltaSec,
        this.interaction.getMoveSpeedMultiplier() * sprintMultiplier * this.skills.getMultiplier("run"),
        this.stamina.isSprinting(),
        this.sceneManager.getCollisionCircles(),
        this.sceneManager.getStaticCollisionMeshes(),
        this.sceneManager.getRaycastExcludedMeshes(),
        this.sceneManager.getCollisionRects(),
      );
      this.flashlight.update(deltaSec);
      this.hintSystem.update(deltaSec);
      this.sceneManager.updateAnimations(deltaSec);
      this.updateZombie(deltaSec);

      const holdingInteract = this.input.isKeyDown("KeyE");
      this.interaction.update(this.sceneManager.getInteractableObjects(), holdingInteract, deltaSec);
      this.shiftManager.update(this.clock.getShiftRemainingSec());

      if (flashlightPressed) this.flashlight.toggle();
      if (interactPressed) {
        if (this.canOpenShop()) this.openShop();
        else this.interaction.interact();
      }
    }

    this.hud.update({
      flashlightChargePercent: this.flashlight.getChargePercent(),
      flashlightOn: this.flashlight.isOn(),
      staminaPercent: this.stamina.getStaminaPercent(),
      remainingSec: this.clock.getShiftRemainingSec(),
      tasks: this.buildHudTasks(),
      interactionPrompt: this.interaction.getInteractionPrompt(),
      // Пока открыт экран (пауза/итоги) — подсказка про захват курсора неуместна,
      // хоть курсор формально и не захвачен.
      pointerLocked:
        this.pauseMenu.isVisible() ||
        this.shiftReportScreen.isVisible() ||
        this.shopScreen.isVisible() ||
        this.input.isPointerLocked(),
      healthPercent: this.health.getHealthPercent(),
      // Полоска жизней не нужна, пока зомби ещё не может появиться — не пугать
      // раньше времени неиспользуемым элементом интерфейса.
      healthVisible: this.zombie.isActive(),
      shopPromptVisible: !this.shopScreen.isVisible() && !this.pauseMenu.isVisible() && this.canOpenShop(),
    });
  }

  /** У двери дома, руки свободны и в прицеле нет ничего, с чем E сделает своё
   *  (починить/поднять) — тогда E открывает магазин. */
  private canOpenShop(): boolean {
    if (this.shiftReportScreen.isVisible() || this.interaction.isCarrying()) return false;
    if (this.interaction.getInteractionPrompt() !== null) return false;
    if (this.shopAnchor === undefined) {
      if (!this.sceneManager.getCurrentLayout()) return false;
      const anchor = this.sceneManager.getShopAnchor();
      this.shopAnchor = anchor ? { x: anchor.x, z: anchor.z } : null;
    }
    if (!this.shopAnchor) return false;
    const { x, z } = this.camera.position;
    return Math.hypot(x - this.shopAnchor.x, z - this.shopAnchor.z) <= SHOP_RADIUS;
  }

  /** Магазин открыт — игра и таймер смены стоят (как на паузе), курсор отпущен. */
  private openShop(): void {
    if (this.shopScreen.isVisible() || this.pauseMenu.isVisible() || !this.canOpenShop()) return;
    this.shopScreen.show(this.buildShopState());
    this.hud.setHidden(true);
    this.lookBeforeShop.yaw = this.camera.rotation.y;
    this.lookBeforeShop.pitch = this.camera.rotation.x;
    if (this.shopAnchor) {
      // Камера Three.js смотрит вдоль -Z: yaw = atan2(-dx, -dz) для направления (dx, dz).
      const dx = this.camera.position.x - this.shopAnchor.x;
      const dz = this.camera.position.z - this.shopAnchor.z;
      this.camera.rotation.y = Math.atan2(-dx, -dz);
      this.camera.rotation.x = SHOP_VIEW_PITCH;
    }
    this.clock.pause();
    this.input.exitPointerLock();
  }

  private closeShop(): void {
    if (!this.shopScreen.isVisible()) return;
    this.shopScreen.hide();
    this.hud.setHidden(false);
    this.camera.rotation.y = this.lookBeforeShop.yaw;
    this.camera.rotation.x = this.lookBeforeShop.pitch;
    this.clock.resume();
    this.input.requestPointerLock();
  }

  private buySkill(id: SkillId): void {
    const cost = this.skills.getUpgradeCost(id);
    if (cost === null || !this.wallet.trySpend(cost)) return;
    this.skills.upgrade(id);
    this.applySkillEffects();
    this.shopScreen.update(this.buildShopState());
    trackEvent({ name: "skill_upgrade", skill: id, level: this.skills.getLevel(id) });
    this.persistEconomy();
  }

  private buildShopState(): ShopState {
    const skills = {} as ShopState["skills"];
    for (const skill of SKILLS) {
      skills[skill.id] = { level: this.skills.getLevel(skill.id), cost: this.skills.getUpgradeCost(skill.id) };
    }
    return { coins: this.wallet.getCoins(), skills };
  }

  /** Множители навыков в системы (бег — прямо в Game.update через скорость). */
  private applySkillEffects(): void {
    this.playerController.setJumpHeightMultiplier(this.skills.getMultiplier("jump"));
    this.flashlight.setDurationMultiplier(this.skills.getMultiplier("flashlight"));
    this.health.setMaxHealthMultiplier(this.skills.getMultiplier("health"));
    this.stamina.setRegenMultiplier(this.skills.getMultiplier("stamina"));
    this.interaction.setWorkSpeedMultiplier(this.skills.getMultiplier("lockpick"));
  }

  private onTaskCompleted(): void {
    this.wallet.add(TASK_REWARD);
    this.coinsThisShift += TASK_REWARD;
    this.persistEconomy();
  }

  /** Двигает зомби к игроку (если он уже появился — см. startShift) и снимает жизни,
   *  если подошёл слишком близко; при полном исчерпании жизней проваливает смену
   *  тем же путём, что и исчерпание времени (ShiftManager.failShift). */
  private updateZombie(deltaSec: number): void {
    if (!this.zombie.isActive()) return;

    const activeShiftIndex = this.shiftManager.getCurrentConfig()?.shiftIndex ?? ZOMBIE_APPEARS_AT_SHIFT;
    const distance = this.zombie.update(
      deltaSec,
      this.camera.position,
      activeShiftIndex,
      this.sceneManager.getCollisionCircles(),
      this.sceneManager.getCollisionRects(),
      this.sceneManager.getStaticCollisionMeshes(),
      this.sceneManager.getRaycastExcludedMeshes(),
    );

    const damagePerSecond = this.zombie.isWithinAttackRange(distance) ? this.zombie.getDamagePerSecond() : 0;
    this.health.damage(damagePerSecond, deltaSec);
    if (this.health.isDead()) this.shiftManager.failShift("caught_by_zombie");
  }

  private buildHudTasks(): HUDTask[] {
    const config = this.shiftManager.getCurrentConfig();
    if (!config) return [];

    const completed = this.shiftManager.getCompletedTaskIds();
    return config.tasks.map((task) => {
      const objectId = this.sceneManager.getBaseObjectId(task.instanceId);
      return {
        label: objectId ? formatTaskLabel(objectId, task.state) : `${task.instanceId} (${task.state})`,
        done: completed.has(task.instanceId),
      };
    });
  }

  private togglePause(): void {
    if (this.pauseMenu.isVisible()) {
      this.pauseMenu.hide();
      this.clock.resume();
      // Без этого пришлось бы ещё раз кликать по канвасу, чтобы заново поймать
      // курсор — браузер сам снимает pointer lock при открытии паузы (Escape).
      this.input.requestPointerLock();
    } else {
      this.pauseMenu.show();
      this.clock.pause();
    }
  }

  private startShift(): void {
    const layout = this.sceneManager.getCurrentLayout();
    if (!layout) {
      console.warn("[Game] startShift() called without a loaded zone");
      return;
    }

    this.playerController.teleportTo(layout.spawnPoint);

    // Раскладка не должна быть одинаковой каждую смену — переставляем, кто где
    // стоит (надгробия между собой, горшки между собой), до того как выбираем
    // задания смены, чтобы они уже ссылались на актуальные позиции.
    this.sceneManager.reshufflePlacedObjects();
    this.sceneManager.applyShiftDarkness(this.currentShiftIndex);

    const config = getShiftConfig(this.currentShiftIndex, layout.zoneId, layout.objects);
    this.shiftManager.startShift(config);

    // Жизни — полный запас на каждую смену (как заряд фонарика/стамина), иначе
    // поражение от зомби в одной смене тянулось бы шлейфом в следующую. Зомби
    // появляется один раз на ZOMBIE_APPEARS_AT_SHIFT и дальше остаётся активным
    // во всех следующих сменах подряд (повторный activate() — no-op).
    this.health.reset();
    this.coinsThisShift = 0;
    if (this.currentShiftIndex >= ZOMBIE_APPEARS_AT_SHIFT) {
      void this.zombie.activate(this.camera.position);
    }

    // ShiftManager уже перевёл объекты в MISSING в ObjectStateMachine — здесь только
    // физически "роняем" соответствующий инстанс в точку spawnPosition (в траву рядом).
    for (const task of config.tasks) {
      if (task.state === ObjectState.MISSING && task.spawnPosition) {
        this.sceneManager.relocateInstance(task.instanceId, task.spawnPosition);
      }
    }

    this.clock.startShiftTimer(config.timeLimitSec);
    this.clock.resume();
    trackEvent({ name: "shift_start", shiftIndex: this.currentShiftIndex });
    this.shiftReportScreen.hide();
    // Курсор был отпущен под клик по кнопке "следующая смена" — захватываем обратно,
    // чтобы не заставлять игрока кликать по канвасу ещё раз в начале смены.
    this.input.requestPointerLock();

    this.currentShiftIndex += 1;
  }

  private onShiftEnd(reason: ShiftEndReason): void {
    this.clock.pause();
    this.interaction.forceDropCarried();
    // Экран итогов смены кликабелен — без этого пришлось бы жать Escape вручную,
    // чтобы вообще увидеть курсор и нажать кнопку на экране итогов.
    this.input.exitPointerLock();

    const config = this.shiftManager.getCurrentConfig();
    const shiftIndex = config?.shiftIndex ?? 0;
    // Смена проиграна, если время вышло, а не все задачи выполнены (all_tasks_done
    // возможен только когда они все закрыты — см. ShiftManager.handleStateChange).
    // Раньше currentShiftIndex уже был инкрементирован в startShift() ДО этого
    // момента и ничем не откатывался при поражении — "следующая смена" на экране
    // итогов вела на shiftIndex+1, даже если игрок не выполнил задания текущей.
    // Теперь при поражении откатываем к 1-й смене: игра начинается заново, а не
    // продолжается с того места, где не вышло уложиться в срок.
    const won = reason === "all_tasks_done";
    if (won) {
      const bonus = shiftCompletionBonus(shiftIndex);
      this.wallet.add(bonus);
      this.coinsThisShift += bonus;
      this.persistEconomy();
    }
    if (!won) {
      this.currentShiftIndex = 1;
      // Следующая попытка снова начнётся с 1-й смены, до ZOMBIE_APPEARS_AT_SHIFT —
      // зомби там быть не должно (появится заново, когда смены дойдут до неё).
      this.zombie.deactivate();
    }
    trackEvent({ name: "shift_end", shiftIndex, reason });
    this.persistShiftProgress(this.currentShiftIndex);

    this.shiftReportScreen.show({
      won,
      reason,
      tasksCompleted: this.shiftManager.getCompletedCount(),
      tasksTotal: config?.tasks.length ?? 0,
      timeSpentSec: config ? config.timeLimitSec - this.clock.getShiftRemainingSec() : 0,
      // Формула очков не определена в ТЗ — временно используем число
      // выполненных задач, пока не появится реальная система подсчёта.
      score: this.shiftManager.getCompletedCount(),
      coinsEarned: this.coinsThisShift,
    });
  }

  /** nextShiftIndex — какая смена начнётся по кнопке на экране итогов (currentShiftIndex
   *  на момент вызова: следующая по порядку при победе, 1 — после отката при поражении
   *  в onShiftEnd). Сохраняем его напрямую, а не "завершённая смена + 1" — иначе при
   *  поражении на экране итогов сохранился бы номер проваленной смены, и возврат в игру
   *  после перезагрузки страницы начинался бы с неё же, а не с первой. */
  private persistShiftProgress(nextShiftIndex: number): void {
    this.persist({ shiftIndex: nextShiftIndex });
  }

  private persistEconomy(): void {
    this.persist({ coins: this.wallet.getCoins(), skills: this.skills.getLevels() });
  }

  private persist(patch: Partial<SaveData>): void {
    this.saveQueue = this.saveQueue
      .then(async () => {
        const current = await this.saveSystem.load();
        this.saveSystem.save({ ...current, ...patch });
      })
      .catch((error) => console.error("[Game] save failed", error));
  }

  private onResize(): void {
    const { clientWidth, clientHeight } = this.canvas;
    this.renderer.setSize(clientWidth, clientHeight, false);
    this.postProcessing.setSize(clientWidth, clientHeight);
    this.camera.aspect = clientWidth / clientHeight;
    this.camera.updateProjectionMatrix();
  }
}
