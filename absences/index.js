import "./index.scss"

import ReactDOM from "react-dom"
import React from "react"

import {Absences} from "./absences"

function getTimeBoundaries(absences) {
  let minStartsOn = null
  let maxEndsOn = null

  absences.forEach(({absences}) => {
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

function getDateList(start, end) {
  let list = []
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
  let {absencesByPerson, reasonList} = JSON.parse(
    document.getElementById("absences-data").textContent
  )

  absencesByPerson = absencesByPerson.map(person => ({
    name: person[0].fullName,
    id: "" + person[0].id,
    absences: person[1].map(a => ({
      ...a,
      startsOn: a.startsOn * 1000,
      endsOn: a.endsOn * 1000,
    })),
  }))

  const timeBoundaries = getTimeBoundaries(absencesByPerson)

  const dateList = getDateList(
    new Date(timeBoundaries.start),
    new Date(timeBoundaries.end)
  )

  const el = document.querySelector("#absences-root")
  ReactDOM.render(
    <Absences
      absencesByPerson={absencesByPerson}
      timeBoundaries={timeBoundaries}
      dateList={dateList}
      reasonList={reasonList}
    />,
    el
  )
})
