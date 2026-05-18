const LEVEL_COLORS = {
  all:          { color: '#657b83', deep: '#586e75' },
  basic:        { color: '#65a30d', deep: '#4d7c0f' },
  intermediate: { color: '#b45309', deep: '#92400e' },
  advanced:     { color: '#c0392b', deep: '#922b21' },
};
function applyLevelColor(level) {
  const c = LEVEL_COLORS[level] || LEVEL_COLORS.all;
  document.documentElement.style.setProperty('--level-color', c.color);
  document.documentElement.style.setProperty('--level-deep', c.deep);
}
