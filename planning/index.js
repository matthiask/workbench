import "./style.scss"

import ReactDOM from "react-dom"
import React, {createContext, useContext, useLayoutEffect, useRef} from "react"

const clamp = (min, max) => (value) => Math.max(Math.min(value, max), min)
const opacityClamp = clamp(0.3, 1)
const identity = (t) => t
export const gettext = window.gettext || identity
const fixed = (s, decimalPlaces) => parseFloat(s).toFixed(decimalPlaces)

document.addEventListener("DOMContentLoaded", () => {
  const data = JSON.parse(document.querySelector("#planning-data").textContent)
  const el = document.querySelector("#planning-root")
  ReactDOM.render(<Planning data={data} />, el)
})

const RowContext = createContext()

const FIRST_DATA_ROW = 3
const FIRST_DATA_COLUMN = 5

function months(weeks) {
  const months = []
  let month = null
  for (let index = 0; index < weeks.length; ++index) {
    let week = weeks[index]
    if (week.month !== month) {
      month = week.month
      months.push({index, month})
    }
  }
  return months
}

function Planning({data}) {
  const gridRef = useRef(null)
  const rowCtx = {
    __row: FIRST_DATA_ROW,
    current: function () {
      return this.__row
    },
    next: function () {
      return ++this.__row
    },
  }

  useLayoutEffect(() => {
    gridRef.current.style.gridTemplateRows = `repeat(${rowCtx.current()}, var(--default-height))`
  }, [])

  return (
    <RowContext.Provider value={rowCtx}>
      <div
        ref={gridRef}
        className="planning"
        style={{
          gridTemplateColumns: `var(--title-column-width) var(--action-width) var(--range-width) var(--hours-total-width) repeat(${
            1 + data.weeks.length
          }, var(--week-width))`,
        }}
      >
        {data.weeks.map((_, idx) => {
          return idx % 2 ? null : (
            <Cell
              key={idx}
              row="1"
              rowspan="-1"
              column={FIRST_DATA_COLUMN + idx}
              className="planning--stripe4"
            />
          )
        })}
        {months(data.weeks).map((month, idx) => (
          <Cell
            key={idx}
            className="planning--scale pl-3"
            row={1}
            column={FIRST_DATA_COLUMN + month.index}
          >
            <strong>{month.month}</strong>
          </Cell>
        ))}
        {data.weeks.map((week, idx) => (
          <Cell
            key={idx}
            className="planning--scale text-center"
            row={2}
            column={FIRST_DATA_COLUMN + idx}
          >
            <strong>{week.day}</strong>
          </Cell>
        ))}

        <Cell
          row={3}
          column={1}
          colspan="span 4"
          className="planning--scale text-right pr-2"
        >
          <strong>{gettext("Hours per week")}</strong>
        </Cell>
        {data.by_week.map((hours, idx) => (
          <Cell
            key={idx}
            row={3}
            column={FIRST_DATA_COLUMN + idx}
            className="planning--range planning--small is-total"
            style={{
              opacity: opacityClamp(0.3 + parseFloat(hours) / 20),
            }}
          >
            <strong>{fixed(hours, 1)}</strong>
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
  ctx.next() // Skip one row
  const row = ctx.next()
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
      </Cell>
      <Cell row={row} column={2}>
        <a
          className="planning--add-pw"
          data-toggle="ajaxmodal"
          title={gettext("Add planned work")}
          href={project.creatework}
        >
          +
        </a>
      </Cell>
      <Cell
        row={row}
        column={3}
        className="planning--small text-center"
        style={{whiteSpace: "nowrap"}}
      >
        {project.range}
      </Cell>
      <Cell row={row} column={4} className="planning--small text-right">
        {`${fixed(project.worked_hours, 0)}h / ${fixed(
          project.planned_hours,
          0
        )}h`}
      </Cell>
      {by_week.map((hours, idx) => {
        hours = parseFloat(hours)
        if (!hours) return null

        return (
          <Cell
            key={idx}
            row={row}
            column={FIRST_DATA_COLUMN + idx}
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
        <Offer key={idx} {...offer} />
      ))}
    </>
  )
}

function Offer({offer, planned_works}) {
  const ctx = useContext(RowContext)
  const row = ctx.next()

  return (
    <>
      <div
        style={{
          gridRow: row,
          gridColumn: `1 / -1`,
        }}
        className="planning--stripe2"
      />
      {offer.id ? (
        <>
          <Cell row={row} column={1} className="planning--title is-offer pl-3">
            <a href={offer.url} target="_blank" rel="noreferrer">
              {offer.title}
            </a>
          </Cell>
          <Cell row={row} column={2}>
            <a
              className="planning--add-pw"
              data-toggle="ajaxmodal"
              title={gettext("Add planned work")}
              href={offer.creatework}
            >
              +
            </a>
          </Cell>
        </>
      ) : (
        <Cell row={row} column={1} className="planning--title is-offer pl-3">
          {gettext("Not part of an offer")}
        </Cell>
      )}
      <Cell
        row={row}
        column={3}
        className="planning--small text-center"
        style={{whiteSpace: "nowrap"}}
      >
        {offer.range}
      </Cell>
      <Cell row={row} column={4} className="planning--small text-right">
        {`${fixed(offer.worked_hours, 0)}h / ${fixed(offer.planned_hours, 0)}h`}
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
  const row = ctx.next()
  const isRequest = !!planned_work.requested_hours
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
        className={`planning--title ${
          isRequest ? "is-pr font-italic" : "is-pw"
        } planning--small pl-5`}
      >
        <a href={planned_work.url} data-toggle="ajaxmodal">
          {planned_work.title}
        </a>
      </Cell>
      <Cell
        row={row}
        column={3}
        className="planning--small text-center"
        style={{whiteSpace: "nowrap"}}
      >
        {planned_work.range}
      </Cell>
      <Cell row={row} column={4} className="planning--small text-right">
        {isRequest
          ? `${fixed(planned_work.missing_hours, 0)}h / ${fixed(
              planned_work.requested_hours,
              0
            )}h`
          : `${fixed(planned_work.planned_hours, 0)}h`}
      </Cell>
      {findContiguousWeekRanges(hours_per_week).map((range, idx) => (
        <Cell
          key={idx}
          row={row}
          column={FIRST_DATA_COLUMN + range.start}
          colspan={`span ${range.length}`}
          className={`planning--range planning--small ${
            isRequest ? "is-pr" : "is-pw"
          }`}
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
      length: hours_per_week.length - rangeStart,
    })
  }

  console.log({ranges})

  return ranges
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
