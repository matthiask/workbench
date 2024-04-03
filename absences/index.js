import "./index.scss"

import ReactDOM from "react-dom"
import React from "react"

import { Absences } from "./absences"

function getDateList(start, end) {
  const list = []
  let currentDate = start

  while (currentDate <= end) {
    list.push(currentDate)
    // create a new (duplicate) date object so the new one can be altered without changing the first one
    currentDate = new Date(currentDate.getTime())
    currentDate.setDate(currentDate.getDate() + 1)
  }

  list.push(currentDate) // we need one more date for one more column grid line

  return list
}

document.addEventListener("DOMContentLoaded", () => {
  const { absencesByPerson, reasonList, timeBoundaries } = JSON.parse(
    document.getElementById("absences-data").textContent,
  )

  const dateList = getDateList(
    new Date(timeBoundaries.start),
    new Date(timeBoundaries.end),
  )

  const el = document.querySelector("#absences-root")
  ReactDOM.render(
    <Absences
      absencesByPerson={absencesByPerson}
      timeBoundaries={timeBoundaries}
      dateList={dateList}
      reasonList={reasonList}
    />,
    el,
  )
})
