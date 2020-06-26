import "./style.scss"

import ReactDOM from "react-dom"
import React, {createContext, useContext, useLayoutEffect, useRef} from "react"

const clamp = (min, max) => (value) => Math.max(Math.min(value, max), min)
const opacityClamp = clamp(0.3, 1)
const identity = (t) => t
export const gettext = window.gettext || identity

document.addEventListener("DOMContentLoaded", () => {
  const data = JSON.parse(document.querySelector("#planning-data").textContent)
  const el = document.querySelector("#planning-root")
  ReactDOM.render(<Planning data={data} />, el)
})

const RowContext = createContext()

const WEEK_START = 4

function Planning({data}) {
  const gridRef = useRef(null)
  const rowCtx = {row: WEEK_START}

  useLayoutEffect(() => {
    gridRef.current.style.gridTemplateRows = `repeat(${rowCtx.row}, var(--default-height))`
  }, [])

  return (
    <RowContext.Provider value={rowCtx}>
      <div
        ref={gridRef}
        className="planning"
        style={{
          gridTemplateColumns: `var(--title-column-width) var(--range-width) var(--hours-total-width) repeat(${
            1 + data.weeks.length
          }, var(--week-width))`,
        }}
      >
        <Cell row={1} column={1} className="planning--scale">
          <strong>{gettext("Calendar week")}</strong>
        </Cell>
        {data.weeks.map((_, idx) => {
          return idx % 2 ? null : (
            <Cell
              key={idx}
              row="1"
              rowspan="-1"
              column={WEEK_START + idx}
              className="planning--stripe4"
            />
          )
        })}
        {data.weeks.map((week, idx) => (
          <Cell
            key={week.week}
            className="planning--scale text-center"
            row={1}
            column={WEEK_START + idx}
            title={`${week.date_from} – ${week.date_until}`}
          >
            <strong>{week.week}</strong>
          </Cell>
        ))}

        <Cell row={2} column={1} className="planning--scale">
          <strong>{gettext("Hours per week")}</strong>
        </Cell>
        {data.by_week.map((hours, idx) => (
          <Cell
            key={idx}
            row={2}
            column={WEEK_START + idx}
            className="planning--range planning--small is-total"
            style={{
              opacity: opacityClamp(0.3 + parseFloat(parseFloat(hours) / 20)),
            }}
          >
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
      <Cell
        row={row}
        column={2}
        className="planning--small text-center"
        style={{whiteSpace: "nowrap"}}
      >
        {project.range}
      </Cell>
      <Cell row={row} column={3} className="planning--small text-center">
        {parseFloat(project.planned_hours).toFixed(0)}h
      </Cell>
      {by_week.map((hours, idx) => {
        hours = parseFloat(hours)
        if (!hours) return null

        return (
          <Cell
            key={idx}
            row={row}
            column={WEEK_START + idx}
            className="planning--range planning--small is-project"
            style={{
              opacity: opacityClamp(0.3 + hours / 20),
            }}
          >
            {hours.toFixed(1)}
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
        {offer.id ? (
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
      <Cell
        row={row}
        column={2}
        className="planning--small text-center"
        style={{whiteSpace: "nowrap"}}
      >
        {offer.range}
      </Cell>
      <Cell row={row} column={3} className="planning--small text-center">
        {parseFloat(offer.planned_hours).toFixed(0)}h
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
        <a href={planned_work.url} data-toggle="ajaxmodal">
          {planned_work.title}
        </a>
      </Cell>
      <Cell
        row={row}
        column={2}
        className="planning--small text-center"
        style={{whiteSpace: "nowrap"}}
      >
        {planned_work.range}
      </Cell>
      <Cell row={row} column={3} className="planning--small text-center">
        {parseFloat(planned_work.planned_hours).toFixed(0)}h
      </Cell>
      {findContiguousWeekRanges(hours_per_week).map((range, idx) => (
        <Cell
          key={idx}
          row={row}
          column={WEEK_START + range.start}
          colspan={`span ${range.length}`}
          className="planning--range planning--small is-work"
          tag="a"
          href={planned_work.url}
          data-toggle="ajaxmodal"
        />
      ))}
    </>
  )
}

function findContiguousWeekRanges(hours_per_week) {
  hours_per_week = hours_per_week.map((hours) => parseFloat(hours))

  let rangeStart = -1
  // const ranges = [{start: 0, length: hours_per_week.length - 1}]
  // return ranges

  let ranges = []

  for (let i = 0; i < hours_per_week.length; ++i) {
    if (hours_per_week[i]) {
      if (rangeStart < 0) {
        // Start new range
        rangeStart = i
      }
    } else {
      if (rangeStart >= 0) {
        ranges.push({start: rangeStart, length: i - rangeStart})
        rangeStart = -1
      }
    }
  }

  if (rangeStart >= 0) {
    ranges.push({
      start: rangeStart,
      length: hours_per_week.length - 1 - rangeStart,
    })
  }

  return ranges
}

function AddPlannedWorkLink({params}) {
  return (
    <a
      className="planning--add-pw"
      href={`/planning/work/create/?${params || ""}`}
      title={gettext("Add planned work")}
      data-toggle="ajaxmodal"
    >
      +
    </a>
  )
}

function Cell({
  row,
  column,
  rowspan = "span 1",
  colspan = "span 1",
  tag = "div",
  children,
  style = {},
  ...props
}) {
  return React.createElement(
    tag,
    {
      style: {
        gridRow: `${row} / ${rowspan}`,
        gridColumn: `${column} / ${colspan}`,
        ...style,
      },
      ...props,
    },
    children
  )
}
