import React, {useState, useMemo} from "react"

import {formatDate, slugify, readableDate, getWeekNumber} from "./utils"

const getColumnName = t => `date-${formatDate(new Date(t))}`
const getRowName = slug => `person-${slug}`

const MONTHS = [
  "Januar",
  "Februar",
  "März",
  "April",
  "Mai",
  "Juni",
  "Juli",
  "August",
  "September",
  "Oktober",
  "November",
  "Dezember",
]

export const Absences = ({absencesByPerson, dateList}) => {
  const scaleValues = useMemo(
    () =>
      dateList.reduce((acc, date) => {
        const week = getWeekNumber(date)[1]

        const entryOfSameWeek = acc.find(e => e.week === week)
        const entryOfSameMonth = acc.find(e => e.month === date.getMonth())
        const entryOfSameYear = acc.find(e => e.year === date.getFullYear())

        if (entryOfSameWeek) {
          return acc
        }

        acc.push({
          week: !entryOfSameWeek ? week : "",
          month: !entryOfSameMonth ? date.getMonth() : "",
          year: !entryOfSameYear ? date.getFullYear() : "",
          date: date,
        })

        return acc
      }, []),
    [dateList]
  )

  return (
    <React.Fragment>
      <style>
        {`
          .absences {
            --day-column-width: .5rem;
            --day-column-offset:
              ${dateList.findIndex(d => d === scaleValues[1].date) - 7};
            --person-row-height: 2rem;
            --person-count: ${absencesByPerson.length};
            --day-count: ${dateList.length};

            grid-template-columns:
              [names] var(--name-column-width)
              ${dateList
                .map(d => `[${getColumnName(d)}] var(--day-column-width)`)
                .join("\n")};
            grid-template-rows:
              [scale] var(--scale-row-height)
              ${absencesByPerson
                .map(p => `[person-${p.slug}] var(--person-row-height)`)
                .join("\n")};
          }
        `}
      </style>
      <div className="absences">
        <Scale scaleValues={scaleValues} />
        {absencesByPerson.map(person => (
          <React.Fragment key={person.slug}>
            <Person person={person} />
            {person.absences.map(a => (
              <Absence
                key={`${person.name}-${a.startsOn}-${a.endsOn}-${a.reason}`}
                absence={a}
                person={person}
              />
            ))}
          </React.Fragment>
        ))}
      </div>
    </React.Fragment>
  )
}

const Person = ({person}) => {
  const style = {
    gridRow: `${getRowName(person.slug)} / span 1`,
  }

  return (
    <div className="absences__person" style={style}>
      {person.name}
    </div>
  )
}

const Absence = ({absence, person}) => {
  const [showPopup, setShowPopup] = useState(false)
  const {startsOn, endsOn} = absence
  const style = {
    gridColumn: `${getColumnName(startsOn)} / ${getColumnName(endsOn)}`,
    gridRowStart: getRowName(person.slug),
  }

  return (
    <div
      className={`absence absence--${slugify(absence.reason)}`}
      style={style}
      title={`${absence.reason} – ${absence.description}`}
      onMouseEnter={() => {
        setShowPopup(true)
      }}
      onMouseLeave={() => {
        setShowPopup(false)
      }}
    >
      <span className="absence__label">
        {absence.reason + " / " + absence.description}
      </span>
      {showPopup ? <Popup absence={absence} /> : null}
    </div>
  )
}

const Popup = ({absence}) => {
  return (
    <div className="absence__popup">
      <strong>{absence.reason}</strong>
      <hr />
      <p>
        {readableDate(new Date(absence.startsOn))} –{" "}
        {readableDate(new Date(absence.endsOn))} <br />
        Beschreibung: {absence.description} <br />
        Tage: {absence.days}d <br />
      </p>
    </div>
  )
}

const Scale = ({scaleValues}) => {
  return (
    <React.Fragment>
      {scaleValues.map(entry => {
        const style = {
          gridColumn: `${getColumnName(entry.date)} / span 1`,
        }

        return (
          <div key={entry.date} className="absences__scale-tick" style={style}>
            {entry.year}
            <br />
            {MONTHS[entry.month]}
            <br />
            {entry.week}
          </div>
        )
      })}
    </React.Fragment>
  )
}
