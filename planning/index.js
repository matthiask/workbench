import "./style.scss"

import ReactDOM from "react-dom"
import React, {createContext, useContext} from "react"

const identity = (t) => t
export const gettext = window.gettext || identity

document.addEventListener("DOMContentLoaded", () => {
  const data = JSON.parse(document.querySelector("#planning-data").textContent)
  const el = document.querySelector("#planning-root")
  ReactDOM.render(<Planning data={data} />, el)
})

const RowContext = createContext()

function Planning({data}) {
  return (
    <RowContext.Provider value={{row: 2}}>
      <div
        className="planning"
        style={{
          gridTemplateColumns: `var(--title-column-width) repeat(${
            1 + data.weeks.length
          }, var(--week-width))`,
        }}
      >
        <Cell row={1} column={1} className="planning--scale">
          <strong>{gettext("Calendar week")}</strong>
        </Cell>
        {data.weeks.map((week, idx) => (
          <Cell
            key={week.week}
            className="planning--scale text-right"
            row={1}
            column={2 + idx}
            title={`${week.date_from} – ${week.date_until}`}
          >
            <strong>{week.week}</strong>
          </Cell>
        ))}

        <Cell row={2} column={1} className="planning--scale">
          <strong>{gettext("Hours per week")}</strong>
        </Cell>
        {data.by_week.map((hours, idx) => (
          <Cell key={idx} className="text-right" row={2} column={2 + idx}>
            <strong>{parseFloat(hours).toFixed(1)}</strong>
          </Cell>
        ))}

        {data.projects_offers.map((project) => (
          <Project key={project.project.id} {...project} />
        ))}
      </div>
    </RowContext.Provider>
  )

  // {JSON.stringify(data)}
}

function Project({by_week, offers, project}) {
  const ctx = useContext(RowContext)
  ++ctx.row // Skip one row
  const row = ++ctx.row
  return (
    <>
      <div
        style={{
          gridRow: row,
          gridColumn: `1 / -1`,
        }}
        className="planning--stripe1"
      />
      <Cell row={row} column={1} className="planning--title is-project">
        <a href={project.url} target="_blank" rel="noreferrer">
          <strong>{project.title}</strong>
        </a>
        <AddPlannedWorkLink params={`project=${project.id}`} />
      </Cell>
      {by_week.map((hours, idx) => {
        if (!parseFloat(hours)) return null

        return (
          <Cell
            key={idx}
            row={row}
            column={2 + idx}
            className="text-right planning--small"
          >
            <strong>{hours}</strong>
          </Cell>
        )
      })}
      {offers.map((offer, idx) => (
        <Offer key={idx} project={project} {...offer} />
      ))}
    </>
  )
}

function Offer({project, offer, planned_works}) {
  const ctx = useContext(RowContext)
  const row = ++ctx.row

  return (
    <>
      <div
        style={{
          gridRow: row,
          gridColumn: `1 / -1`,
        }}
        className="planning--stripe2"
      />
      <Cell row={row} column={1} className="planning--title is-offer pl-3">
        {offer ? (
          <>
            <a href={offer.url} target="_blank" rel="noreferrer">
              {offer.title}
            </a>
            <AddPlannedWorkLink
              params={`project=${project.id}&offer=${offer.id}`}
            />
          </>
        ) : (
          gettext("Not part of an offer")
        )}
      </Cell>
      {planned_works.map((planned_work, idx) => (
        <PlannedWork
          key={planned_work.planned_work.id}
          {...planned_work}
          isEven={(1 + idx) % 2 === 0}
        />
      ))}
    </>
  )
}

function PlannedWork({planned_work, hours_per_week, isEven}) {
  const ctx = useContext(RowContext)
  const row = ++ctx.row
  return (
    <>
      {isEven ? (
        <div
          style={{gridRow: row, gridColumn: "1 / -1"}}
          className="planning--stripe3"
        />
      ) : null}
      <Cell
        row={row}
        column={1}
        className="planning--title is-pw planning--small pl-5"
      >
        <a href={planned_work.update_url} data-toggle="ajaxmodal">
          {planned_work.title}
        </a>
      </Cell>
      {hours_per_week.map((hours, idx) => {
        if (!parseFloat(hours)) return null
        return (
          <Cell
            key={idx}
            row={row}
            column={2 + idx}
            className="planning--small text-right"
          >
            {hours}
          </Cell>
        )
      })}
    </>
  )
}

function AddPlannedWorkLink({params}) {
  return (
    <a
      className="planning--add-pw"
      href={`/planning/work/create/?${params || ""}`}
      title={gettext("Add planned work")}
      data-toggle="ajaxmodal"
    >
      +{/*→ {gettext("Add work")}*/}
    </a>
  )
}

function Cell({row, column, children, ...props}) {
  return (
    <div
      style={{gridRow: `${row} / span 1`, gridColumn: `${column} / span 1`}}
      {...props}
    >
      {children}
    </div>
  )
}
