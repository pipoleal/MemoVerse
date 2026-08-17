"use client";

import { motion } from "framer-motion";

export default function Hero() {
  return (
    <section className="relative z-10 flex flex-col items-center px-6 text-center">
      <motion.p
        initial={{ opacity: 0, y: 20, filter: "blur(10px)" }}
        animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
        transition={{ duration: 1, delay: 0.2 }}
        className="mb-6 uppercase tracking-[0.4em] text-yellow-400"
      >
        Welcome to
      </motion.p>

      <motion.h1
        initial={{ opacity: 0, y: 30, filter: "blur(12px)" }}
        animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
        transition={{ duration: 1.2, delay: 0.5 }}
        className="bg-linear-to-r from-white via-slate-200 to-yellow-300 bg-clip-text text-7xl font-black tracking-tight text-transparent md:text-8xl lg:text-9xl"
      >
        MemoVerse
      </motion.h1>

      <motion.p
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 1, delay: 0.8 }}
        className="mt-6 max-w-2xl text-lg text-gray-300 md:text-2xl"
      >
        Every memory becomes a star.
      </motion.p>
    </section>
  );
}