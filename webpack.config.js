const crypto = require("node:crypto")
const crypto_orig_createHash = crypto.createHash
crypto.createHash = (algorithm) =>
  crypto_orig_createHash(algorithm === "md4" ? "sha1" : algorithm)

const merge = require("webpack-merge")
const config = require("fh-webpack-config")

const path = require("node:path")
const DEBUG = process.env.NODE_ENV !== "production"
const HOST = process.env.HOST || "127.0.0.1"
const HTTPS = !!process.env.HTTPS

module.exports = merge.smart(
  config.commonConfig,
  // config.chunkSplittingConfig,
  config.reactConfig,
  {
    context: path.join(__dirname),
    // devtool: "source-map",
    output: {
      path: path.resolve("./static/workbench/"),
      publicPath: DEBUG
        ? `http${HTTPS ? "s" : ""}://${HOST}:4000/`
        : `${process.env.STATIC_URL || "/static/"}workbench/`,
      filename: DEBUG ? "[name].js" : "[name]-[contenthash].js",
    },
  },
)

// Smart webpack merging is not smart enough to remove the default `main` entrypoint
module.exports.entry = {
  timer: "./timer/index.js",
  absences: "./absences/index.js",
  planning: "./planning/index.js",
}
