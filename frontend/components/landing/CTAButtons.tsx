"use client";

import { motion } from "framer-motion";
import { useRouter } from "next/navigation";

import Button from "../ui/Button";

export default function CTAButtons() {
  const router = useRouter();

  return (
    <motion.div
      initial={{ opacity: 0, y: 25 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{
        duration: 1,
        delay: 1.1,
      }}
      className="mt-12 flex flex-col justify-center gap-5 sm:flex-row"
    >
      <Button
        variant="primary"
        onClick={() => {
          router.push("/experience/new");
        }}
      >
        ⭐ Start Experience
      </Button>

      <Button
        variant="secondary"
        onClick={() => {
          router.push("/login");
        }}
      >
        🌌 My Galaxy
      </Button>
    </motion.div>
  );
}