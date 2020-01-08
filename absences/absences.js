import React from "react"

import {formatDate} from "./utils"

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
  const {startsOn, endsOn} = absence
  const style = {
    gridColumn: `${getColumnName(startsOn)} / ${getColumnName(endsOn)}`,
    gridRowStart: getRowName(person.slug),
  }

  return (
    <div
      className="absences__absence"
      style={style}
      title={`${person.name} – ${absence.reason} – ${absence.description}`}
    >
      {absence.reason + " / " + absence.description}
    </div>
  )
}
