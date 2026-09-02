export type Star = {
  id: number;
  size: number;
  top: number;
  left: number;
  opacity: number;
  duration: number;
  delay: number;
};

export function generateStars(quantity: number): Star[] {
  return Array.from({ length: quantity }, (_, index) => ({
    id: index,
    size: Math.random() * 3 + 1,
    top: Math.random() * 100,
    left: Math.random() * 100,
    opacity: Math.random(),
    duration: Math.random() * 4 + 2,
    delay: Math.random() * 5,
  }));
}