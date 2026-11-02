// DOM 렌더링 (사용자 입력은 textContent로만 삽입)
(function () {
  const { formatKoreanDate, formatShortDate, parseKey, addDays, truncate } = window.TodoUtils;

  const PRIORITY_LABEL = { high: '높음', medium: '보통', low: '낮음' };
  const EMPTY_TEXT = {
    all: '오늘 할 일을 추가해 보세요',
    active: '남은 할일이 없어요. 수고했어요!',
    done: '아직 완료한 할일이 없어요',
  };

  const $ = (id) => document.getElementById(id);
  let renderedIds = null; // 새로 나타난 항목에만 등장 애니메이션을 주기 위함

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function createItem(todo, animate) {
    const li = el('li', 'item' + (todo.done ? ' done' : '') + (animate ? ' enter' : ''));
    li.dataset.id = todo.id;
    li.dataset.priority = todo.priority;
    li.draggable = true;

    const handle = el('span', 'handle', '⋮⋮');
    handle.setAttribute('aria-hidden', 'true');

    const check = el('input', 'check');
    check.type = 'checkbox';
    check.checked = todo.done;
    check.setAttribute('aria-label', `${todo.text} ${todo.done ? '완료 취소' : '완료'}`);

    const dot = el('button', 'dot');
    dot.type = 'button';
    dot.title = `우선순위: ${PRIORITY_LABEL[todo.priority]}`;
    dot.setAttribute('aria-label', `우선순위 ${PRIORITY_LABEL[todo.priority]}, 눌러서 변경`);

    const text = el('span', 'text', todo.text);

    const edit = el('button', 'item-btn edit', '✎');
    edit.type = 'button';
    edit.setAttribute('aria-label', `${todo.text} 수정`);

    const del = el('button', 'item-btn delete', '×');
    del.type = 'button';
    del.setAttribute('aria-label', `${todo.text} 삭제`);

    li.append(handle, check, dot, text, edit, del);
    return li;
  }

  function progressMessage(done, total) {
    if (total === 0) return '아직 할일이 없어요';
    const pct = Math.round((done / total) * 100);
    if (done === total) return `${done} / ${total} 완료 (100%) · 모두 끝냈어요! 🎉`;
    return `${done} / ${total} 완료 (${pct}%)`;
  }

  function render(state, store) {
    $('today').textContent = formatKoreanDate(parseKey(state.today));

    // 진행률
    const { total, done } = store.getStats();
    const pct = total ? Math.round((done / total) * 100) : 0;
    $('progressFill').style.width = pct + '%';
    $('progressBar').setAttribute('aria-valuenow', String(pct));
    $('progressText').textContent = progressMessage(done, total);

    // 필터 탭
    document.querySelectorAll('[data-filter]').forEach((btn) => {
      const active = btn.dataset.filter === state.filter;
      btn.classList.toggle('active', active);
      btn.setAttribute('aria-selected', String(active));
    });

    // 목록
    const items = store.getTodayTodos();
    const prev = renderedIds;
    $('list').replaceChildren(...items.map((t) => createItem(t, prev !== null && !prev.has(t.id))));
    renderedIds = new Set(items.map((t) => t.id));

    const empty = $('empty');
    empty.hidden = items.length > 0;
    empty.textContent = EMPTY_TEXT[state.filter];

    // 푸터
    $('remaining').textContent = `남은 할일 ${total - done}개`;
    $('clearDone').disabled = done === 0;

    // 배너
    $('storageBanner').hidden = state.storageOk;
    const carryCount = state.carryCandidates.length;
    $('carryBanner').hidden = carryCount === 0;
    if (carryCount) {
      const when = state.carryFrom === addDays(state.today, -1)
        ? '어제'
        : `${formatShortDate(parseKey(state.carryFrom))}에`;
      $('carryText').textContent = `${when} 못한 할일 ${carryCount}개를 오늘로 가져올까요?`;
    }
  }

  function renderHistory(groups) {
    const body = $('historyBody');
    if (!groups.length) {
      body.replaceChildren(el('p', 'empty', '지난 기록이 없어요'));
      return;
    }
    body.replaceChildren(
      ...groups.map(({ date, todos }) => {
        const section = el('section', 'history-day');
        const doneCount = todos.filter((t) => t.done).length;
        const heading = el('h3', null, formatKoreanDate(parseKey(date)) + ' ');
        heading.append(el('span', 'count', `${doneCount} / ${todos.length} 완료`));

        const list = el('ul', 'history-list');
        todos.forEach((t) => {
          const li = el('li', 'history-item' + (t.done ? ' done' : ''));
          li.dataset.priority = t.priority;
          const mark = el('span', 'mark', t.done ? '✓' : '○');
          mark.setAttribute('aria-label', t.done ? '완료' : '미완료');
          li.append(mark, el('span', 'pdot'), el('span', 'text', t.text));
          if (t.carried) li.append(el('span', 'tag', '이월됨'));
          list.append(li);
        });

        section.append(heading, list);
        return section;
      })
    );
  }

  function showToast(text) {
    $('toastText').textContent = text;
    $('toast').hidden = false;
  }

  function hideToast() {
    $('toast').hidden = true;
  }

  function celebrate() {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    const box = $('celebrate');
    const colors = ['#ef4444', '#f59e0b', '#10b981', '#3b82f6', '#8b5cf6', '#ec4899'];
    const pieces = [];
    for (let i = 0; i < 48; i++) {
      const piece = el('span', 'confetti');
      piece.style.left = Math.random() * 100 + '%';
      piece.style.background = colors[i % colors.length];
      piece.style.animationDelay = Math.random() * 0.4 + 's';
      piece.style.animationDuration = 1.6 + Math.random() * 1.2 + 's';
      piece.style.setProperty('--drift', Math.random() * 200 - 100 + 'px');
      piece.style.setProperty('--spin', Math.random() * 720 - 360 + 'deg');
      pieces.push(piece);
    }
    box.replaceChildren(...pieces);
    setTimeout(() => box.replaceChildren(), 3400);
  }

  window.TodoRender = { render, renderHistory, showToast, hideToast, celebrate, truncate };
})();
