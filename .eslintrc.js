module.exports = {
  env: {
    browser: true,
    es6: true,
    jquery: true,
    node: true,
  },
  extends: [
    "eslint:recommended",
    "plugin:prettier/recommended",
    "plugin:react/recommended",
  ],
  globals: {
    Atomics: "readonly",
    SharedArrayBuffer: "readonly",
    __API_HOST: "readonly",
  },
  parserOptions: {
    ecmaFeatures: {
      jsx: true,
    },
    ecmaVersion: 2018,
    sourceType: "module",
  },
  plugins: ["react", "prettier"],
  rules: {
    "prettier/prettier": "error",
    "react/display-name": 0,
    "react/prop-types": 0,
    "no-unused-vars": [
      "error",
      {
        argsIgnorePattern: "^_",
        varsIgnorePattern: "React",
      },
    ],
    "react/prop-types": "off",
    "react/display-name": "off",
  },
  settings: {
    react: {
      version: "16.6",
    },
  },
}
