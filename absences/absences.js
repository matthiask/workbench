import React from "react"

export const Absences = ({data}) => {
  return (
    <div className="absences">
      {data.map(person => (
        <Person key={person[0]} data={person} />
      ))}
    </div>
  )
}

const Person = ({data}) => (
  <div className="absences__person">
    {data[0]}
    {data[1].map(a => (
      <Absence
        key={`${data[0]}-${a.startsOn}-${a.endsOn}-${a.reason}`}
        data={a}
      />
    ))}
  </div>
)

const Absence = ({data}) => {
  const {startsOn, endsOn} = data

  return (
    <div className="absences__absence">
      {data.reason + " / " + data.description}
    </div>
  )
}
