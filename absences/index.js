import "./index.scss"

import ReactDOM from "react-dom"
import React from "react"

import {Absences} from "./absences"

function getTimeBoundaries(absences) {
  let minStartsOn = null
  let maxEndsOn = null

  absences.forEach(([_person, absences]) => {
    absences.forEach(a => {
      if (minStartsOn === null || minStartsOn > a.startsOn) {
        minStartsOn = a.startsOn
      }

      if (maxEndsOn === null || maxEndsOn < a.endsOn) {
        maxEndsOn = a.endsOn
      }
    })
  })

  return {
    start: minStartsOn,
    end: maxEndsOn,
  }
}

document.addEventListener("DOMContentLoaded", () => {
  const absences = JSON.parse(
    document.getElementById("absences-data").textContent
  )

  const timeBoundaries = getTimeBoundaries(absences)

  const el = document.querySelector("#absences-root")
  ReactDOM.render(
    <Absences data={absences} timeBoundaries={timeBoundaries} />,
    el
  )
})
