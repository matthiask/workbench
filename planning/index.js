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
    <RowContext.Provider value={{row: 1}}>
      <div
        className="planning"
        style={{
          gridTemplateColumns: `var(--title-column-width) repeat(${
            1 + data.weeks.length
          }, var(--week-width))`,
        }}
      >
        <div
          className="planning--scale"
          style={{gridRow: `1 / span 1`, gridColumn: `1 / span 1`}}
        >
          {gettext("Calendar week")}
        </div>
        {data.weeks.map((week, idx) => (
          <Cell
            key={week.week}
            className="planning--scale text-right"
            row={1}
            column={2 + idx}
          >
            {week.week}
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
      <Cell row={row} column={1}>
        <a href={project.url} target="_blank">
          <strong>{project.title}</strong>
        </a>
      </Cell>
      {by_week.map((hours, idx) => (
        <Cell key={idx} row={row} column={2 + idx} className="text-right">
          <strong>{hours}</strong>
        </Cell>
      ))}
      {offers.map((offer, idx) => (
        <Offer key={idx} {...offer} />
      ))}
      <AddPlannedWorkCell column={1} params={`project=${project.id}`} />
    </>
  )
}

function Offer({offer, planned_works}) {
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
      <Cell row={row} column={1} className="planning--offer pl-3">
        {offer ? (
          <a href={offer.url} target="_blank">
            {offer.title}
          </a>
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
      <Cell row={row} column={1} className="planning--pw pl-5">
        <a href={planned_work.update_url} data-toggle="ajaxmodal">
          {planned_work.title}
        </a>
      </Cell>
      {hours_per_week.map((hours, idx) => (
        <Cell
          key={idx}
          row={row}
          column={2 + idx}
          className="planning--pw text-right"
        >
          {hours}
        </Cell>
      ))}
    </>
  )
}

function AddPlannedWorkCell({params, ...props}) {
  const ctx = useContext(RowContext)
  const row = ++ctx.row
  return (
    <Cell row={row} {...props} className="planning--pw is-create pl-5 mb-3">
      <a
        href={`/planning/work/create/?${params || ""}`}
        data-toggle="ajaxmodal"
      >
        → {gettext("Add work")}
      </a>
    </Cell>
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
