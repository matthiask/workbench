const path = require("path")
const webpack = require("webpack")
const BundleTracker = require("webpack-bundle-tracker")
const {CleanWebpackPlugin} = require("clean-webpack-plugin")
const packageJson = require(path.resolve(__dirname, "package.json"))
// const Visualizer = require("webpack-visualizer-plugin")

const HOST = process.env.HOST || "127.0.0.1"
const DEBUG = process.env.NODE_ENV !== "production"
const HTTPS = !!process.env.HTTPS

function cssLoader(firstLoader) {
  return [
    "style-loader",
    "css-loader",
    {
      loader: "postcss-loader",
      options: {
        plugins: [
          require("autoprefixer")(),
          require("cssnano")({preset: "default"}),
        ],
        sourceMap: true,
      },
    },
  ]
    .concat(firstLoader || [])
    .filter(function(el) {
      return !!el
    })
}

module.exports = {
  mode: DEBUG ? "development" : "production",
  context: path.join(__dirname, "timer"),
  // devtool: "source-map",
  entry: {
    main: "./index.js",
  },
  output: {
    path: path.resolve("./static/workbench/timer/"),
    publicPath: DEBUG
      ? "http" + (HTTPS ? "s" : "") + "://" + HOST + ":4000/"
      : (process.env.STATIC_URL || "/static/") + "workbench/timer/",
    filename: DEBUG ? "[name].js" : "[name]-[contenthash].js",
  },
  module: {
    rules: [
      {
        test: /\.jsx?$/,
        exclude: /node_modules/,
        use: [
          {
            loader: "babel-loader",
            options: {
              presets: [
                [
                  "@babel/preset-env",
                  {
                    modules: false,
                    // debug: true,
                    targets: packageJson.browserslist,
                    useBuiltIns: "usage",
                    corejs: "3",
                  },
                ],
                "@babel/preset-react",
              ],
              plugins: [
                "@babel/plugin-proposal-object-rest-spread",
                "@babel/plugin-proposal-class-properties",
              ],
              cacheDirectory: path.resolve(__dirname, "tmp"),
              sourceType: "unambiguous",
            },
          },
        ],
      },
      {
        test: /\.css$/,
        use: cssLoader(),
      },
      {
        test: /\.scss$/,
        use: cssLoader({
          loader: "sass-loader",
          options: {
            sassOptions: {
              includePaths: [
                path.resolve(path.join(__dirname, "node_modules")),
              ],
            },
          },
        }),
      },
      {
        test: /\.less$/,
        use: cssLoader("less-loader"),
      },
      {
        test: /\.(png|woff|woff2|svg|eot|ttf|gif|jpe?g)$/,
        use: [
          {
            loader: "url-loader",
            options: {
              limit: 500,
              // ManifestStaticFilesStorage reuse.
              name: "[path][name].[md5:hash:hex:12].[ext]",
              // No need to emit files in production, collectstatic does it.
              emitFile: DEBUG,
            },
          },
        ],
      },
    ],
  },
  resolve: {
    extensions: [".js", ".jsx"],
    modules: ["node_modules", "."],
    alias: {},
  },
  plugins: [
    DEBUG ? null : new CleanWebpackPlugin(),
    new BundleTracker({
      filename: "./static/webpack-stats-" + (DEBUG ? "dev" : "prod") + ".json",
    }),
    DEBUG
      ? new webpack.NamedModulesPlugin()
      : new webpack.HashedModuleIdsPlugin(),
    // DEBUG ? null : new Visualizer(),
  ].filter(function(el) {
    return !!el
  }),
  devServer: {
    contentBase: false,
    inline: true,
    quiet: false,
    https: HTTPS,
    disableHostCheck: true,
    headers: {"Access-Control-Allow-Origin": "*"},
    host: HOST,
    port: 4000,
  },
  performance: {
    // No point warning in development, since HMR / CSS bundling blows up
    // the asset / entrypoint size anyway.
    hints: DEBUG ? false : "warning",
  },
}
