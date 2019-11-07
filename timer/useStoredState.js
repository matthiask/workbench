import {useEffect, useState} from "react"
import {localStorage} from "./storage.js"

export function useStoredState({key, version}) {
  const chuckOld = data => {
    /* versioning of watch list data structure */
    let new_ = data || {}
    if (new_._v != version) {
      new_ = {}
    }
    new_._v = version
    return new_
  }

  const [state, setStateWithoutLS] = useState(() => {
    let data
    try {
      data = JSON.parse(localStorage.getItem(key))
    } catch (e) {
      /* nothing */
    }
    return chuckOld(data)
  })

  const setState = data => {
    setStateWithoutLS(data)
    localStorage.setItem(key, JSON.stringify(data))
  }

  useEffect(() => {
    window.addEventListener("storage", e => {
      if (e.key === key) {
        setStateWithoutLS(chuckOld(JSON.parse(e.newValue)))
      }
    })
  }, [])

  return [state, setState]
}
