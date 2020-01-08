import "./index.scss"

import ReactDOM from "react-dom"
import React from "react"

import {formatDate, slugify} from "./utils"

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
    currentDate = new Date(currentDate.setDate(currentDate.getDate() + 1))
  }

  return list
}

document.addEventListener("DOMContentLoaded", () => {
  let absencesByPerson = JSON.parse(
    document.getElementById("absences-data").textContent
  )

  absencesByPerson = absencesByPerson.map(person => ({
    name: person[0],
    slug: slugify(person[0]),
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
    />,
    el
  )
})
