module.exports = {
  env: {
    browser: true,
    es6: true,
    jquery: true,
    node: true,
  },
  extends: [
    "eslint:recommended",
    "prettier",
    // "prettier/react",
    // "plugin:react/recommended",
  ],
  parser: "babel-eslint",
  parserOptions: {
    ecmaVersion: 2018,
    ecmaFeatures: {
      jsx: true,
    },
    sourceType: "module",
  },
  plugins: [
    "prettier",
    // "react",
    // "react-hooks",
  ],
  rules: {
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
