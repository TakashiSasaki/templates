export const READABLE_WEIGHT_EXPONENT = 0.8;
export const MAX_MIN_SIBLING_SHARE = 0.02;
export const MIN_SHARE_BUDGET = 0.5;
export const TREEMAP_SQUARIFY_RATIO = 1.2;

export function readableWeight(value, exponent = READABLE_WEIGHT_EXPONENT) {
  const normalized = Number.isFinite(value) ? Math.max(0, value) : 0;
  return normalized === 0 ? 0 : normalized ** exponent;
}

export function normalizedSiblingWeights(values, targetTotal = 1) {
  if (!values.length) return [];
  const raw = values.map((value) => readableWeight(value));
  const rawTotal = raw.reduce((sum, value) => sum + value, 0);
  if (rawTotal <= 0) return values.map(() => targetTotal / values.length);

  const minimumShare = Math.min(MAX_MIN_SIBLING_SHARE, MIN_SHARE_BUDGET / values.length);
  const floor = rawTotal * minimumShare;
  const adjusted = raw.map((value) => Math.max(value, floor));
  const adjustedTotal = adjusted.reduce((sum, value) => sum + value, 0);
  return adjusted.map((value) => targetTotal * value / adjustedTotal);
}

export function assignReadableHierarchyValues(root, valueAccessor) {
  const assignChildren = (node, targetValue) => {
    node.value = targetValue;
    if (!node.children?.length) return;
    const childWeights = normalizedSiblingWeights(
      node.children.map((child) => valueAccessor(child.data)),
      targetValue
    );
    node.children.forEach((child, index) => assignChildren(child, childWeights[index]));
  };

  root.value = 1;
  if (!root.children?.length) return root;

  const topWeights = normalizedSiblingWeights(
    root.children.map((child) => valueAccessor(child.data)),
    root.value
  );
  root.children.forEach((child, index) => assignChildren(child, topWeights[index]));
  return root;
}
