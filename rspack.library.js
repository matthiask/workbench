/*
Somewhat reusable webpack configuration chunks

A basic rspack file may looks as follows:

    module.exports = (env, argv) => {
      const {
        base,
        devServer,
        assetRule,
        postcssRule,
        swcWithPreactRule,
        resolvePreactAsReact,
      } = require("./rspack.library.js")(argv.mode === "production")

      return {
        ...base,
        ...resolvePreactAsReact(),
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
            swcWithPreactRule(),
          ],
        },
      }
    }

NOTE: PLEASE DO NOT EVER UPDATE THIS FILE WITHOUT CONTRIBUTING THE CHANGES BACK
TO FH-FABLIB AT https://github.com/feinheit/fh-fablib

*/

const path = require("node:path")
const fs = require("node:fs")
const HtmlWebpackPlugin = require("html-webpack-plugin")
const rspack = require("@rspack/core")

const truthy = (...list) => list.filter((el) => !!el)

function coreJsVersion() {
  try {
    const { version } = JSON.parse(
      fs.readFileSync(
        path.join(__dirname, "node_modules/core-js/package.json"),
      ),
    )
    const [major, minor] = version.split(".")
    return `${major}.${minor}`
  } catch (_err) {
    return "3"
  }
}

module.exports = (PRODUCTION) => {
  const cwd = process.cwd()

  function swcWithPreactRule() {
    return {
      test: /\.(j|t)sx?$/,
      loader: "builtin:swc-loader",
      exclude: [/[\\/]node_modules[\\/]|foundation/],
      options: {
        jsc: {
          parser: {
            syntax: "ecmascript",
            jsx: true,
          },
          transform: {
            react: {
              runtime: "automatic",
              importSource: "preact",
            },
          },
          externalHelpers: true,
        },
        env: {
          mode: "usage",
          coreJs: coreJsVersion(),
        },
      },
      type: "javascript/auto",
    }
  }

  function swcWithReactRule() {
    return {
      test: /\.(j|t)sx?$/,
      loader: "builtin:swc-loader",
      exclude: [/[\\/]node_modules[\\/]|foundation/],
      options: {
        jsc: {
          parser: {
            syntax: "ecmascript",
            jsx: true,
          },
          transform: {
            react: {
              runtime: "automatic",
              // importSource: "preact",
            },
          },
          externalHelpers: true,
        },
        env: {
          mode: "usage",
          coreJs: coreJsVersion(),
        },
      },
      type: "javascript/auto",
    }
  }

  function htmlPlugin(name = "", config = {}) {
    return new HtmlWebpackPlugin({
      filename: name ? `${name}.html` : "[name].html",
      inject: false,
      templateContent: ({ htmlWebpackPlugin }) =>
        `${htmlWebpackPlugin.tags.headTags}`,
      ...config,
    })
  }

  function htmlSingleChunkPlugin(chunk = "") {
    return htmlPlugin(chunk, chunk ? { chunks: [chunk] } : {})
  }

  function postcssLoaders(plugins) {
    return [
      { loader: rspack.CssExtractRspackPlugin.loader },
      { loader: "css-loader" },
      { loader: "postcss-loader", options: { postcssOptions: { plugins } } },
    ]
  }

  function cssExtractPlugin() {
    return new rspack.CssExtractRspackPlugin({
      filename: PRODUCTION ? "[name].[contenthash].css" : "[name].css",
      chunkFilename: PRODUCTION ? "[name].[contenthash].css" : "[name].css",
    })
  }

  return {
    truthy,
    base: {
      // mode: PRODUCTION ? "production" : "development",
      // bail: PRODUCTION,
      context: path.join(cwd, "frontend"),
      entry: { main: "./main.js" },
      output: {
        clean: PRODUCTION,
        path: path.join(cwd, PRODUCTION ? "static" : "tmp"),
        publicPath: "/static/",
        filename: PRODUCTION ? "[name].[contenthash].js" : "[name].js",
        // Same as the default but prefixed with "_/[name]."
        assetModuleFilename: "_/[name].[hash][ext][query][fragment]",
      },
      plugins: truthy(cssExtractPlugin(), htmlSingleChunkPlugin()),
      target: "browserslist:defaults",
    },
    devServer(proxySettings) {
      return {
        host: "0.0.0.0",
        hot: true,
        port: Number(process.env.PORT || 4000),
        allowedHosts: "all",
        client: {
          overlay: {
            errors: true,
            warnings: false,
            runtimeErrors: true,
          },
        },
        devMiddleware: {
          headers: { "Access-Control-Allow-Origin": "*" },
          index: true,
          writeToDisk: (path) => /\.html$/.test(path),
        },
        proxy: [
          proxySettings
            ? {
                context: () => true,
                target: `http://127.0.0.1:${proxySettings.backendPort}`,
              }
            : {},
        ],
      }
    },
    assetRule() {
      return {
        test: /\.(png|webp|woff2?|svg|eot|ttf|otf|gif|jpe?g|mp3|wav)$/i,
        type: "asset",
        parser: { dataUrlCondition: { maxSize: 512 /* bytes */ } },
      }
    },
    postcssRule(cfg) {
      return {
        test: /\.css$/i,
        type: "javascript/auto",
        use: postcssLoaders(cfg?.plugins),
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
        type: "javascript/auto",
      }
    },
    swcWithPreactRule,
    swcWithReactRule,
    resolvePreactAsReact() {
      return {
        resolve: {
          alias: {
            react: "preact/compat",
            "react-dom/test-utils": "preact/test-utils",
            "react-dom": "preact/compat", // Must be below test-utils
            "react/jsx-runtime": "preact/jsx-runtime",
          },
        },
      }
    },
    htmlPlugin,
    htmlSingleChunkPlugin,
    postcssLoaders,
    cssExtractPlugin,
  }
}
