import { ObjectState, type ShiftConfig } from "@/data/types";
import { ObjectStateMachine } from "@/systems/ObjectStateMachine";

export type ShiftEndReason = "time_out" | "all_tasks_done" | "caught_by_zombie";

export class ShiftManager {
  private currentConfig: ShiftConfig | null = null;
  private readonly completedTaskIds = new Set<string>();
  private ended = false;

  constructor(
    private readonly stateMachine: ObjectStateMachine,
    private readonly onShiftEnd: (reason: ShiftEndReason) => void = () => {},
    /** Каждая выполненная задача текущей смены — для награды монетами (Game). */
    private readonly onTaskCompleted: (instanceId: string) => void = () => {},
  ) {
    this.stateMachine.onChange((instanceId, state) => this.handleStateChange(instanceId, state));
  }

  startShift(config: ShiftConfig): void {
    // Незавершённые задачи прошлой смены (время вышло раньше, чем игрок успел)
    // иначе остались бы испорченными навсегда и не по заданию — новая смена их
    // не перечисляет повторно (ShiftConfig.tasks переизбирается заново), а
    // ObjectStateMachine ничего сама не забывает. ended=true на время сброса,
    // чтобы handleStateChange не принял эти NORMAL-переходы за выполнение задач
    // ещё активной (на этот момент) прошлой смены и не вызвал onShiftEnd повторно.
    if (this.currentConfig) {
      this.ended = true;
      for (const task of this.currentConfig.tasks) {
        if (!this.completedTaskIds.has(task.instanceId)) {
          this.stateMachine.transition(task.instanceId, ObjectState.NORMAL);
        }
      }
    }

    this.currentConfig = config;
    this.completedTaskIds.clear();
    this.ended = false;
    for (const task of config.tasks) {
      this.stateMachine.transition(task.instanceId, task.state);
    }
  }

  /** Вызывать каждый кадр с Clock.getShiftRemainingSec(). */
  update(remainingSec: number): void {
    if (this.ended || !this.currentConfig) return;
    if (remainingSec <= 0) this.endShift("time_out");
  }

  /** Проваливает смену извне (игрока поймал зомби — см. Game.update()/ZombieSystem) —
   *  тот же путь завершения, что и time_out: пауза, сброс currentShiftIndex на 1,
   *  экран "Смена провалена". Без эффекта, если смена уже закончилась. */
  failShift(reason: Exclude<ShiftEndReason, "all_tasks_done">): void {
    if (this.ended || !this.currentConfig) return;
    this.endShift(reason);
  }

  isShiftComplete(): boolean {
    if (!this.currentConfig) return false;
    return this.currentConfig.tasks.every((task) => this.completedTaskIds.has(task.instanceId));
  }

  getCurrentConfig(): ShiftConfig | null {
    return this.currentConfig;
  }

  getCompletedCount(): number {
    return this.completedTaskIds.size;
  }

  getCompletedTaskIds(): ReadonlySet<string> {
    return this.completedTaskIds;
  }

  private handleStateChange(instanceId: string, state: ObjectState): void {
    if (this.ended || !this.currentConfig) return;
    if (state !== ObjectState.NORMAL) return;

    const isTrackedTask = this.currentConfig.tasks.some((task) => task.instanceId === instanceId);
    if (!isTrackedTask || this.completedTaskIds.has(instanceId)) return;

    this.completedTaskIds.add(instanceId);
    this.onTaskCompleted(instanceId);
    if (this.isShiftComplete()) this.endShift("all_tasks_done");
  }

  private endShift(reason: ShiftEndReason): void {
    this.ended = true;
    this.onShiftEnd(reason);
  }
}
