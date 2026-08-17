import { Stars } from "@react-three/drei";

export default function Scene() {
  return (
    <>
      <color attach="background" args={["#020617"]} />

      <ambientLight intensity={0.8} />

      <Stars
        radius={250}
        depth={80}
        count={12000}
        factor={6}
        saturation={0}
        fade
        speed={0.35}
      />
    </>
  );
}