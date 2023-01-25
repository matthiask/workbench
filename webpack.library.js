/*
Somewhat reusable webpack configuration chunks

A basic webpack file may looks as follows:

    module.exports = (env, argv) => {
      const { base, devServer, assetRule, postcssRule, babelWithPreactRule } =
        require("./webpack.library.js")(argv.mode === "production")

      return {
        ...base,
        devServer: devServer({ backendPort: env.backend }),
        module: {
          rules: [
            assetRule(),
            postcssRule({
              plugins: [
                "postcss-nested",
                "postcss-import",
                "postcss-custom-media",
                "autoprefixer",
              ],
            }),
            babelWithPreactRule(),
          ],
        },
      }
    }

NOTE: PLEASE DO NOT EVER UPDATE THIS FILE WITHOUT CONTRIBUTING THE CHANGES BACK
TO FH-FABLIB AT https://github.com/feinheit/fh-fablib
*/

const path = require("path")
const MiniCssExtractPlugin = require("mini-css-extract-plugin")
const CssMinimizerPlugin = require("css-minimizer-webpack-plugin")
const HtmlWebpackPlugin = require("html-webpack-plugin")
const HtmlInlineScriptPlugin = require("html-inline-script-webpack-plugin")

const truthy = (...list) => list.filter((el) => !!el)

module.exports = (PRODUCTION) => {
  const cwd = process.cwd()

  function babelRule({ presets, plugins } = {}) {
    const options = {
      cacheDirectory: true,
      presets: [
        [
          "@babel/preset-env",
          { useBuiltIns: "usage", corejs: "3.25", targets: "defaults" },
        ],
      ],
      plugins: plugins || [],
    }
    if (presets) {
      options.presets = [...options.presets, ...presets]
    }
    if (plugins) {
      options.plugins = plugins
    }
    return {
      test: /\.m?js$/i,
      exclude: /(node_modules)/,
      use: {
        loader: "babel-loader",
        options,
      },
    }
  }

  function miniCssExtractPlugin() {
    return new MiniCssExtractPlugin({
      filename: PRODUCTION ? "[name].[contenthash].css" : "[name].css",
    })
  }

  function htmlPlugin(name = "", config = {}) {
    const debug = PRODUCTION ? "" : "debug."
    config = {
      filename: name ? `${debug}${name}.html` : `${debug}[name].html`,
      templateContent: "<head></head>",
      ...config,
    }
    return new HtmlWebpackPlugin(config)
  }

  function htmlSingleChunkPlugin(chunk = "") {
    return htmlPlugin(chunk, chunk ? { chunks: [chunk] } : {})
  }

  function htmlInlineScriptPlugin() {
    return PRODUCTION
      ? new HtmlInlineScriptPlugin({
          scriptMatchPattern: [/runtime.*\.js$/],
        })
      : null
  }

  function postcssLoaders(plugins) {
    return [
      PRODUCTION ? MiniCssExtractPlugin.loader : { loader: "style-loader" },
      { loader: "css-loader" },
      { loader: "postcss-loader", options: { postcssOptions: { plugins } } },
    ]
  }

  return {
    truthy,
    base: {
      mode: PRODUCTION ? "production" : "development",
      bail: PRODUCTION,
      devtool: PRODUCTION ? "source-map" : "eval-source-map",
      context: path.join(cwd, "frontend"),
      entry: { main: "./main.js" },
      output: {
        clean: { keep: /\.html$/ },
        path: path.join(cwd, "static"),
        publicPath: "/static/",
        filename: PRODUCTION ? "[name].[contenthash].js" : "[name].js",
        // Same as the default but prefixed with "_/[name]."
        assetModuleFilename: "_/[name].[hash][ext][query]",
      },
      plugins: truthy(
        miniCssExtractPlugin(),
        htmlSingleChunkPlugin(),
        htmlInlineScriptPlugin(),
      ),
      optimization: PRODUCTION
        ? {
            minimizer: ["...", new CssMinimizerPlugin()],
            runtimeChunk: "single",
            splitChunks: {
              chunks: "all",
            },
          }
        : {
            runtimeChunk: "single",
          },
    },
    noSplitting: {
      optimization: PRODUCTION
        ? { minimizer: ["...", new CssMinimizerPlugin()] }
        : {},
    },
    devServer(proxySettings) {
      return {
        host: "0.0.0.0",
        hot: true,
        port: 8000,
        allowedHosts: "all",
        devMiddleware: {
          headers: { "Access-Control-Allow-Origin": "*" },
          index: true,
          writeToDisk: (path) => /\.html$/.test(path),
        },
        proxy: proxySettings
          ? {
              context: () => true,
              target: `http://127.0.0.1:${proxySettings.backendPort}`,
            }
          : {},
      }
    },
    assetRule() {
      return {
        test: /\.(png|woff2?|svg|eot|ttf|otf|gif|jpe?g|mp3|wav)$/i,
        type: "asset",
        parser: { dataUrlCondition: { maxSize: 512 /* bytes */ } },
      }
    },
    postcssRule({ plugins }) {
      return {
        test: /\.css$/i,
        use: postcssLoaders(plugins),
      }
    },
    sassRule(options = {}) {
      let { cssLoaders } = options
      if (!cssLoaders) cssLoaders = postcssLoaders(["autoprefixer"])
      return {
        test: /\.scss$/i,
        use: [
          ...cssLoaders,
          {
            loader: "sass-loader",
            options: {
              sassOptions: {
                includePaths: [path.resolve(path.join(cwd, "node_modules"))],
              },
            },
          },
        ],
      }
    },
    babelRule,
    babelWithPreactRule() {
      return babelRule({
        plugins: [
          [
            "@babel/plugin-transform-react-jsx",
            { runtime: "automatic", importSource: "preact" },
          ],
        ],
      })
    },
    babelWithReactRule() {
      return babelRule({
        presets: [["@babel/preset-react", { runtime: "automatic" }]],
      })
    },
    miniCssExtractPlugin,
    htmlPlugin,
    htmlSingleChunkPlugin,
    htmlInlineScriptPlugin,
    postcssLoaders,
  }
}
