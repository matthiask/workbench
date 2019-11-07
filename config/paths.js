const path = require("path")

module.exports = {
  src: path.resolve(__dirname, "../timer"), // source files
  build: path.resolve(__dirname, "../workbench/static/workbench/lib/timer/"), // production build files
  static: path.resolve(__dirname, "../public"), // static files to copy to build folder,
}
