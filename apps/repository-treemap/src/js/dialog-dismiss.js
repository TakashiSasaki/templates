export function isPointOutsideRect(clientX, clientY, rect) {
  return clientX < rect.left
    || clientX > rect.right
    || clientY < rect.top
    || clientY > rect.bottom;
}
