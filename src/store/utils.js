const snakeToCamel = string =>
  string.replace(/(_\w)/g, match => match[1].toUpperCase())

export function mapSnakeCaseToCamelCase(object) {
  const camelCaseObject = {}

  for (let key in object) {
    camelCaseObject[snakeToCamel(key)] = object[key]
  }

  return camelCaseObject
}

export const containsJSON = response => {
  const contentType = response.headers.get("content-type")

  if (contentType && contentType.includes("application/json")) {
    return true
  } else {
    return false
  }
}
