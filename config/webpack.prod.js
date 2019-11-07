const paths = require("./paths")
const webpack = require("webpack")
const merge = require("webpack-merge")
const common = require("./webpack.common.js")
const TerserJSPlugin = require("terser-webpack-plugin")
const OptimizeCSSAssetsPlugin = require("optimize-css-assets-webpack-plugin")

module.exports = merge(common, {
  mode: "production",
  output: {
    path: paths.build,
    publicPath: "/timerr/",
    filename: "[name].bundle.js",
  },
  // devtool: "source-map",
  plugins: [
    new webpack.DefinePlugin({
      __API_HOST: JSON.stringify("/"),
    }),
  ],
  /**
   * Optimization
   *
   * Production minimizing of JavaSvript and CSS assets.
   */
  optimization: {
    minimizer: [new TerserJSPlugin({}), new OptimizeCSSAssetsPlugin({})],
  },
})
