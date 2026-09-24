export function createLatestSelectionGuard() {
  let revision = 0;

  return {
    begin() {
      revision += 1;
      return revision;
    },
    isCurrent(token) {
      return token === revision;
    }
  };
}
