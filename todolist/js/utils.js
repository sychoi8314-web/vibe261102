// 날짜 포맷, ID 생성 등 공용 함수
(function () {
  const WEEKDAYS = ['일', '월', '화', '수', '목', '금', '토'];

  function pad(n) {
    return String(n).padStart(2, '0');
  }

  // 로컬 시간대 기준 'YYYY-MM-DD'
  function todayKey(date = new Date()) {
    return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
  }

  function parseKey(key) {
    const [y, m, d] = key.split('-').map(Number);
    return new Date(y, m - 1, d);
  }

  function addDays(key, days) {
    const date = parseKey(key);
    date.setDate(date.getDate() + days);
    return todayKey(date);
  }

  // '2026년 11월 2일 (월)'
  function formatKoreanDate(date) {
    return `${date.getFullYear()}년 ${date.getMonth() + 1}월 ${date.getDate()}일 (${WEEKDAYS[date.getDay()]})`;
  }

  // '11월 2일'
  function formatShortDate(date) {
    return `${date.getMonth() + 1}월 ${date.getDate()}일`;
  }

  function uid() {
    if (window.crypto && typeof crypto.randomUUID === 'function') return crypto.randomUUID();
    return Date.now().toString(36) + Math.random().toString(36).slice(2, 10);
  }

  function truncate(text, max) {
    return text.length > max ? text.slice(0, max) + '…' : text;
  }

  window.TodoUtils = { todayKey, parseKey, addDays, formatKoreanDate, formatShortDate, uid, truncate };
})();
