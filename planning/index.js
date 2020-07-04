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

const FIRST_DATA_ROW = 2
const FIRST_DATA_COLUMN = 6

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
          gridTemplateColumns: `var(--title-column-width) var(--action-width) var(--range-width) var(--hours-total-width) var(--user-width) repeat(${
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

        {data.capacity && <Capacity {...data.capacity} />}
        <TotalByWeek by_week={data.by_week} />
        {data.capacity && (
          <DeltaByWeek planned={data.by_week} capacity={data.capacity.total} />
        )}
        {data.projects_offers.map((project) => (
          <Project key={project.project.id} {...project} />
        ))}

        <Absences absences={data.absences} />
      </div>
    </RowContext.Provider>
  )
}

function TotalByWeek({by_week}) {
  const ctx = useContext(RowContext)
  const row = ctx.next()
  return (
    <>
      <Cell
        row={row}
        column={1}
        colspan="span 4"
        className="planning--scale text-right pr-2"
      >
        <strong>{gettext("Planned hours per week")}</strong>
      </Cell>
      {by_week.map((hours, idx) => (
        <Cell
          key={idx}
          row={row}
          column={FIRST_DATA_COLUMN + idx}
          className="planning--range planning--small is-total"
          style={{
            opacity: opacityClamp(0.3 + parseFloat(hours) / 20),
          }}
        >
          {fixed(hours, 1)}
        </Cell>
      ))}
    </>
  )
}

function DeltaByWeek({planned, capacity}) {
  const ctx = useContext(RowContext)
  const row = ctx.next()
  return (
    <>
      <Cell
        row={row}
        column={1}
        colspan="span 4"
        className="planning--scale text-right pr-2"
      >
        <strong>{gettext("Delta")}</strong>
      </Cell>
      {planned.map((hours, idx) => {
        const delta = hours - capacity[idx]

        return (
          <Cell
            key={idx}
            row={row}
            column={FIRST_DATA_COLUMN + idx}
            className="planning--range planning--small is-delta"
            style={{
              backgroundColor:
                delta > 0
                  ? `hsl(0, ${clamp(0, 70)(delta * 5)}%, 70%)`
                  : `hsl(120, ${clamp(0, 50)(-delta * 3)}%, 70%)`,
            }}
          >
            {fixed(delta, 1)}
          </Cell>
        )
      })}
    </>
  )
}

function Capacity({total, by_user}) {
  const ctx = useContext(RowContext)
  const row = ctx.next()

  return (
    <>
      <Cell
        row={row}
        column={1}
        colspan="span 4"
        className="planning--scale text-right pr-2"
      >
        <strong>{gettext("Capacity per week")}</strong>
      </Cell>
      {total.map((hours, idx) => (
        <Cell
          key={idx}
          row={row}
          column={FIRST_DATA_COLUMN + idx}
          className="planning--range planning--small is-capacity"
          style={{
            opacity: opacityClamp(0.3 + parseFloat(hours) / 20),
          }}
        >
          {fixed(hours, 1)}
        </Cell>
      ))}
      {by_user.length > 1
        ? by_user.map((user, idx) => <UserCapacity key={idx} {...user} />)
        : null}
    </>
  )
}

function UserCapacity({user, capacity}) {
  const ctx = useContext(RowContext)
  const row = ctx.next()

  return (
    <>
      <Cell
        row={row}
        column={1}
        colspan="span 4"
        className="planning--scale text-right pr-2"
        tag="a"
        href={user.url}
      >
        {user.name}
      </Cell>
      {capacity.map((hours, idx) => (
        <Cell
          key={idx}
          row={row}
          column={FIRST_DATA_COLUMN + idx}
          className="planning--range planning--small is-user-capacity"
          style={{
            opacity: opacityClamp(0.3 + parseFloat(hours) / 20),
          }}
        >
          {fixed(hours, 1)}
        </Cell>
      ))}
    </>
  )
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
      <Cell row={row} column={2} style={{color: "var(--primary)"}}>
        <a
          className="planning--add-pw"
          data-toggle="ajaxmodal"
          title={gettext("Add planned work")}
          href={project.creatework}
        >
          +
        </a>{" "}
        <a href={project.planning}>
          <svg
            xmlns="http://www.w3.org/2000/svg"
            width="15"
            height="16"
            viewBox="0 0 15 16"
          >
            <path
              fill="currentColor"
              fillRule="evenodd"
              d="M10 12h3V2h-3v10zm-4-2h3V2H6v8zm-4 4h3V2H2v12zm-1 1h13V1H1v14zM14 0H1a1 1 0 0 0-1 1v14a1 1 0 0 0 1 1h13a1 1 0 0 0 1-1V1a1 1 0 0 0-1-1z"
            />
          </svg>
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

function Offer({offer, work_list}) {
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
      {work_list.map((work, idx) => (
        <Work key={work.work.id} {...work} isEven={(1 + idx) % 2 === 0} />
      ))}
    </>
  )
}

function Work({work, hours_per_week, isEven}) {
  const ctx = useContext(RowContext)
  const row = ctx.next()
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
          work.is_request ? "is-pr font-italic" : "is-pw"
        } planning--small pl-5`}
      >
        <a href={work.url} data-toggle="ajaxmodal">
          {work.title}
        </a>
      </Cell>
      <Cell
        row={row}
        column={3}
        className="planning--small text-center"
        style={{whiteSpace: "nowrap"}}
      >
        {work.range}
      </Cell>
      <Cell row={row} column={4} className="planning--small text-right">
        {work.is_request
          ? `${fixed(work.missing_hours, 0)}h / ${fixed(
              work.requested_hours,
              0
            )}h`
          : `${fixed(work.planned_hours, 0)}h`}
      </Cell>
      <Cell row={row} column={5} className="planning--small text-center">
        {work.user}
      </Cell>
      {findContiguousWeekRanges(hours_per_week).map((range, idx) => (
        <Cell
          key={idx}
          row={row}
          column={FIRST_DATA_COLUMN + range.start}
          colspan={`span ${range.length}`}
          className={`planning--range planning--small ${
            work.is_request ? "is-pr" : "is-pw"
          }`}
          tag="a"
          href={work.url}
          data-toggle="ajaxmodal"
        />
      ))}
    </>
  )
}

function Absences({absences}) {
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
        <strong>{gettext("Absences")}</strong>
      </Cell>
      {absences.map((user, idx) => (
        <UserAbsences key={idx} user={user} />
      ))}
    </>
  )
}

function UserAbsences({user}) {
  const ctx = useContext(RowContext)
  const row = ctx.next()

  return (
    <>
      <Cell row={row} column={1} className="planning--title is-absence pl-3">
        {user[0]}
      </Cell>
      {user[1].map((absence, idx) =>
        absence ? (
          <Cell
            key={idx}
            row={row}
            column={FIRST_DATA_COLUMN + idx}
            className="planning--range planning--small is-absence"
            tag="a"
            href={absence.url}
            data-toggle="ajaxmodal"
          ></Cell>
        ) : null
      )}
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
