const path = require("node:path")

module.exports = (env, argv) => {
  const {
    base,
    devServer,
    assetRule,
    sassRule,
    postcssRule,
    swcWithReactRule,
    cssExtractPlugin,
    htmlSingleChunkPlugin,
    truthy,
  } = require("./rspack.library.js")(argv.mode === "production")

  return {
    ...base,
    context: path.resolve(process.cwd()),
    entry: {
      main: "./workbench/static/workbench/app.js",
      timer: "./timer/index.js",
      absences: "./absences/index.js",
      planning: "./planning/index.js",
    },
    devServer: devServer({ backendPort: env.backend }),
    module: {
      rules: [
        assetRule(),
        postcssRule({
          plugins: [
            [
              "@csstools/postcss-global-data",
              { files: ["./frontend/styles/custom-media.css"] },
            ],
            "postcss-custom-media",
            "postcss-nesting",
            "autoprefixer",
          ],
        }),
        sassRule(),
        swcWithReactRule(),
      ],
    },
    plugins: truthy(
      cssExtractPlugin(),
      htmlSingleChunkPlugin("main"),
      htmlSingleChunkPlugin("timer"),
      htmlSingleChunkPlugin("absences"),
      htmlSingleChunkPlugin("planning"),
    ),
  }
}
