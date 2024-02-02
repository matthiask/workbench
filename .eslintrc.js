module.exports = {
  extends: ["preact", "prettier"],
  rules: {
    "no-unused-vars": [
      "error",
      {
        argsIgnorePattern: "^_",
        varsIgnorePattern: "React|Fragment|h|^_",
      },
    ],
  },
}
