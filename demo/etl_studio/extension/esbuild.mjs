import esbuild from "esbuild";

const watch = process.argv.includes("--watch");

const extensionCtx = await esbuild.context({
  entryPoints: ["src/extension.ts"],
  bundle: true,
  platform: "node",
  format: "cjs",
  target: "node20",
  external: ["vscode"],
  outfile: "dist/extension.js",
  sourcemap: true,
});

const webviewCtx = await esbuild.context({
  entryPoints: ["webview/main.tsx"],
  bundle: true,
  platform: "browser",
  format: "iife",
  target: "es2022",
  outfile: "dist/webview.js",
  sourcemap: "inline",
  define: { "process.env.NODE_ENV": '"production"' },
});

if (watch) {
  await Promise.all([extensionCtx.watch(), webviewCtx.watch()]);
  console.log("esbuild watching src/ and webview/ ...");
} else {
  await Promise.all(
    [extensionCtx, webviewCtx].map(async (ctx) => {
      await ctx.rebuild();
      await ctx.dispose();
    })
  );
  console.log("esbuild: dist/extension.js + dist/webview.js built");
}
