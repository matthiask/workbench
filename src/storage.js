/* Inspired by: https://michalzalecki.com/why-using-localStorage-directly-is-a-bad-idea/ */

class Storage {
  constructor(storage) {
    this.fallbackStorage = {}
    this.storage = storage
  }

  getItem(key) {
    try {
      return this.storage.getItem(key)
    } catch (e) {
      return this.fallbackStorage[key] || null
    }
  }

  setItem(key, value) {
    try {
      this.storage.setItem(key, value)
    } catch (e) {
      this.fallbackStorage[key] = value
    }
  }

  removeItem(key) {
    try {
      this.storage.removeItem(key)
    } catch (error) {
      delete this.fallbackStorage[key]
    }
  }
}

export const sessionStorage = new Storage(window.sessionStorage)
export const localStorage = new Storage(window.localStorage)
