const crypto = require("node:crypto")
const crypto_orig_createHash = crypto.createHash
crypto.createHash = (algorithm) =>
  crypto_orig_createHash(algorithm === "md4" ? "sha1" : algorithm)

const path = require("node:path")
const MiniCssExtractPlugin = require("mini-css-extract-plugin")

module.exports = {
  entry: "./app.js",
  mode: "production",
  context: path.resolve(__dirname, "workbench", "static", "workbench"),
  output: {
    filename: "[name].js",
    path: path.resolve(__dirname, "workbench", "static", "workbench", "lib"),
    publicPath: "/static/workbench/",
  },
  plugins: [
    new MiniCssExtractPlugin({
      filename: "[name].css",
    }),
  ],
  module: {
    rules: [
      {
        test: /\.(scss)$/,
        use: [
          {
            // Adds CSS to the DOM by injecting a `<style>` tag
            // loader: 'style-loader'
            loader: MiniCssExtractPlugin.loader,
          },
          {
            // Interprets `@import` and `url()` like `import/require()` and will resolve them
            loader: "css-loader",
          },
          {
            // Loader for webpack to process CSS with PostCSS
            loader: "postcss-loader",
            options: {
              postcssOptions: {
                plugins() {
                  return [require("autoprefixer")]
                },
              },
            },
          },
          {
            // Loads a SASS/SCSS file and compiles it to CSS
            loader: "sass-loader",
            options: {
              sassOptions: {
                includePaths: [
                  path.resolve(path.join(__dirname, "node_modules")),
                ],
              },
            },
          },
        ],
      },
      {
        test: /\.(png|woff|woff2|svg|eot|otf|ttf|gif|jpe?g)$/,
        use: [
          {
            loader: "url-loader",
            options: {
              limit: 500,
              name: "[path][name].[ext]",
              emitFile: false,
            },
          },
        ],
      },
    ],
  },
}
