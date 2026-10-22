/** Показывается, когда игрок использует предмет "Ключ" (InventorySystem) — единственная
 *  на сейчас концовка игры. В отличие от ShiftReportScreen это не промежуточный итог
 *  смены, а финал: кнопка не продолжает игру, а перезапускает её с чистого листа
 *  (как PauseMenu.onExit — другого главного меню в игре нет). */
export class WinScreen {
  private readonly root: HTMLElement;

  constructor(parent: HTMLElement, onRestart: () => void) {
    this.root = document.createElement("div");
    this.root.className = "win-screen";
    this.root.style.display = "none";

    const title = document.createElement("h2");
    title.className = "win-screen__title";
    title.textContent = "Вы нашли выход";

    const text = document.createElement("p");
    text.className = "win-screen__text";
    text.textContent = "Ключ открыл путь из города. Ночной смотритель уходит — живым.";

    const restart = document.createElement("button");
    restart.type = "button";
    restart.className = "win-screen__restart";
    restart.textContent = "Начать заново";
    restart.addEventListener("click", () => onRestart());

    this.root.append(title, text, restart);
    parent.appendChild(this.root);
  }

  show(): void {
    this.root.style.display = "block";
  }

  hide(): void {
    this.root.style.display = "none";
  }

  isVisible(): boolean {
    return this.root.style.display !== "none";
  }
}
