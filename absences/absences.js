import React, {useState} from "react"

import {formatDate, slugify, readableDate} from "./utils"

const getColumnName = t => `date-${formatDate(new Date(t))}`
const getRowName = slug => `person-${slug}`

export const Absences = ({absencesByPerson, dateList}) => {
  return (
    <React.Fragment>
      <style>
        {`
          .absences {
            grid-template-columns:
              [names] 10rem
              ${dateList.map(d => `[${getColumnName(d)}] 1rem`).join("\n")};
            grid-template-rows:
              [scale] 1rem
              ${absencesByPerson
                .map(p => `[person-${p.slug}] 2rem`)
                .join("\n")};
          }
        `}
      </style>
      <div className="absences">
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
      {showPopup ? <Popup absence={absence} person={person} /> : null}
    </div>
  )
}

const Popup = ({person, absence}) => {
  return (
    <div className="absence__popup">
      <p>
        <strong>{absence.reason}</strong>
        <hr />
        {readableDate(new Date(absence.startsOn))} –{" "}
        {readableDate(new Date(absence.endsOn))} <br />
        Beschreibung: {absence.description} <br />
        Tage: {absence.days}d <br />
      </p>
    </div>
  )
}
