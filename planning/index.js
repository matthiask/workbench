import "./style.scss"

import ReactDOM from "react-dom"
import React, {
  createContext,
  useContext,
  useLayoutEffect,
  useRef,
} from "react"

const clamp = (min, value, max) => Math.max(Math.min(value, max), min)
const opacityClamp = (value) => clamp(0.3, value, 1)
const gettext = window.gettext || ((t) => t)
const pgettext = window.pgettext || ((ctx, t) => t)
const interpolate = window.interpolate || ((t) => t)
const fixed = (s, decimalPlaces) => parseFloat(s).toFixed(decimalPlaces)

document.addEventListener("DOMContentLoaded", () => {
  const data = JSON.parse(document.querySelector("#planning-data").textContent)
  const el = document.querySelector("#planning-root")
  ReactDOM.render(<Planning data={data} />, el)
})

const RowContext = createContext()

const FIRST_DATA_ROW = 3
const FIRST_DATA_COLUMN = 6

function months(weeks) {
  const months = []
  let month = null
  for (let index = 0; index < weeks.length; ++index) {
    let week = weeks[index]
    if (week.month !== month) {
      month = week.month
      months.push({ index, month })
    }
  }
  return months
}

function Planning({ data }) {
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
    gridRef.current.style.gridTemplateRows = `14px 16px 16px repeat(${
      rowCtx.current() - 2
    }, var(--default-height))`

    Array.from(document.querySelectorAll(".planning--title a")).forEach(
      (el) => (el.title = el.textContent)
    )
  }, [])

  const plannedAndRequested = data.requested_by_week.map(
    (hours, idx) => parseFloat(hours) + parseFloat(data.by_week[idx])
  )

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
        <Cell
          key="this_week_index"
          row="1"
          rowspan="-1"
          column={FIRST_DATA_COLUMN + data.this_week_index}
          className="planning--this-week"
        />
        {months(data.weeks).map((month, idx) => (
          <Cell
            key={idx}
            className="planning--scale text-center planning--small"
            row={1}
            column={FIRST_DATA_COLUMN + month.index}
          >
            <strong>{month.month}</strong>
          </Cell>
        ))}
        {data.weeks.map((week, idx) => (
          <Cell
            key={idx}
            className="planning--scale text-center planning--small"
            row={2}
            column={FIRST_DATA_COLUMN + idx}
          >
            {week.week}
          </Cell>
        ))}
        {data.weeks.map((week, idx) => (
          <Cell
            key={idx}
            className="planning--scale text-center planning--smaller"
            row={3}
            column={FIRST_DATA_COLUMN + idx}
          >
            {week.period}
          </Cell>
        ))}

        {data.capacity && <Capacity {...data.capacity} />}
        <TotalByWeek
          by_week={data.by_week}
          title={gettext("Planned hours per week")}
        />
        {data.capacity && (
          <>
            <DeltaByWeek
              planned={data.by_week}
              capacity={data.capacity.total}
            />
            <TotalByWeek
              by_week={data.requested_by_week}
              title={gettext("Requested hours per week")}
            />
            <DeltaByWeek
              planned={plannedAndRequested}
              capacity={data.capacity.total}
            />
          </>
        )}
        {data.projects_offers.map((project) => (
          <Project key={project.project.id} {...project} />
        ))}

        <Absences absences={data.absences} />
      </div>
    </RowContext.Provider>
  )
}

function TotalByWeek({ by_week, title }) {
  const ctx = useContext(RowContext)
  const row = ctx.next()
  return (
    <>
      <Cell
        row={row}
        column={1}
        colspan={`span ${FIRST_DATA_COLUMN - 1}`}
        className="planning--scale text-right pr-2"
      >
        <strong>{title}</strong>
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
          {fixed(hours, 0)}
        </Cell>
      ))}
    </>
  )
}

function DeltaByWeek({ planned, capacity }) {
  const ctx = useContext(RowContext)
  const row = ctx.next()
  return (
    <>
      <Cell
        row={row}
        column={1}
        colspan={`span ${FIRST_DATA_COLUMN - 1}`}
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
                  ? `hsl(0, ${clamp(0, delta * 5, 70)}%, 70%)`
                  : `hsl(120, ${clamp(0, -delta * 3, 50)}%, 70%)`,
            }}
          >
            {fixed(delta, 0)}
          </Cell>
        )
      })}
    </>
  )
}

function Capacity({ total, by_user }) {
  const ctx = useContext(RowContext)
  const row = ctx.next()

  return (
    <>
      <Cell
        row={row}
        column={1}
        colspan={`span ${FIRST_DATA_COLUMN - 1}`}
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
          {fixed(hours, 0)}
        </Cell>
      ))}
      {by_user.length > 1
        ? by_user.map((user, idx) => <UserCapacity key={idx} {...user} />)
        : null}
    </>
  )
}

function UserCapacity({ user, capacity }) {
  const ctx = useContext(RowContext)
  const row = ctx.next()

  return (
    <>
      <Cell
        row={row}
        column={1}
        colspan={`span ${FIRST_DATA_COLUMN - 1}`}
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
          {fixed(hours, 0)}
        </Cell>
      ))}
    </>
  )
}

function Project({ by_week, offers, project }) {
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
      <Cell
        row={row}
        column={1}
        className={`planning--title is-project ${
          project.is_closed ? "is-closed" : ""
        }`}
      >
        <a href={project.url} target="_blank" rel="noopener noreferrer">
          <strong>{project.title}</strong>
          {project.is_closed ? <> {gettext("(closed)")}</> : ""}
        </a>
      </Cell>
      <Cell
        row={row}
        column={2}
        style={{ color: "var(--primary)" }}
        className="no-pr"
      >
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
        style={{ whiteSpace: "nowrap" }}
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
      {project.worked_hours ? <WorkedHours project={project} /> : null}
      {offers.map((offer, idx) => (
        <Offer key={idx} {...offer} />
      ))}
    </>
  )
}

function WorkedHours({ project }) {
  const ctx = useContext(RowContext)
  const row = ctx.next()

  return (
    <>
      <Cell row={row} column={1} className="planning--title is-worked no-pr">
        {gettext("Logged hours")}
      </Cell>

      {project.worked_hours.map((hours, idx) => {
        hours = parseFloat(hours)
        if (!hours) return null

        return (
          <Cell
            key={idx}
            row={row}
            column={FIRST_DATA_COLUMN + idx}
            className="planning--range planning--small is-worked no-pr"
            style={{
              opacity: opacityClamp(0.3 + hours / 20),
            }}
          >
            {fixed(hours, 1)}
          </Cell>
        )
      })}
    </>
  )
}

function Offer({ offer, work_list }) {
  const ctx = useContext(RowContext)
  const row = ctx.next()

  const classList = ["planning--title is-offer pl-3"]
  if (offer.is_declined) classList.push("is-declined")
  if (!offer.is_accepted) classList.push("is-not-accepted")

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
          <Cell row={row} column={1} className={classList.join(" ")}>
            <a href={offer.url} target="_blank" rel="noopener noreferrer">
              {offer.title}
              {offer.is_declined ? <> {gettext("(declined)")}</> : ""}
              {!offer.is_accepted && !offer.is_declined ? (
                <> {gettext("(not accepted yet)")}</>
              ) : (
                ""
              )}
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
        style={{ whiteSpace: "nowrap" }}
      >
        {offer.range}
      </Cell>
      <Cell row={row} column={4} className="planning--small text-right">
        {`${fixed(offer.planned_hours, 0)}h`}
      </Cell>
      {work_list.map((work, idx) => (
        <Work key={work.work.id} {...work} isEven={(1 + idx) % 2 === 0} />
      ))}
    </>
  )
}

function Work({ work, hours_per_week, per_week, isEven }) {
  const ctx = useContext(RowContext)
  const row = ctx.next()
  const cls = work.is_request ? "is-request" : "is-pw"
  return (
    <>
      {isEven ? (
        <div
          style={{ gridRow: row, gridColumn: "1 / -1" }}
          className="planning--stripe3"
        />
      ) : null}
      <Cell
        row={row}
        column={1}
        className={`planning--title ${cls} ${
          work.is_provisional ? "is-provisional" : ""
        } planning--small pl-5`}
      >
        <a href={work.url} data-toggle="ajaxmodal">
          {work.title}
        </a>
      </Cell>
      {work.is_provisional ? (
        <Cell
          row={row}
          column={2}
          className={`planning--small ${cls}`}
          title={gettext("is provisional")}
        >
          {pgettext("provisional", "prov.")}
        </Cell>
      ) : null}
      <Cell
        row={row}
        column={3}
        className={`planning--small text-center ${cls}`}
        style={{ whiteSpace: "nowrap" }}
      >
        {work.range}
      </Cell>
      <Cell
        row={row}
        column={4}
        className={`planning--small text-right ${cls}`}
      >
        {work.is_request
          ? `${fixed(work.missing_hours, 0)}h / ${fixed(
              work.requested_hours,
              0
            )}h`
          : `${fixed(work.planned_hours, 0)}h`}
      </Cell>
      <Cell
        row={row}
        column={5}
        className={`planning--small ${
          work.is_request ? "font-italic" : ""
        } text-center no-pr`}
      >
        {work.user}
      </Cell>
      {work.period && (
        <Cell
          key={`${work.id}-period`}
          row={row}
          column={FIRST_DATA_COLUMN + work.period[0]}
          colspan={FIRST_DATA_COLUMN + work.period[1] + 1}
          className={`planning--range is-request ${
            work.is_provisional ? "is-provisional" : ""
          }`}
          tag="a"
          href={work.url}
          data-toggle="ajaxmodal"
          title={interpolate(gettext("%sh per week"), [fixed(per_week, 1)])}
        >
          <span className="no-pr">{work.text}</span>
        </Cell>
      )}
      {hours_per_week &&
        findContiguousWeekRanges(hours_per_week).map((range, idx) => (
          <Cell
            key={idx}
            row={row}
            column={FIRST_DATA_COLUMN + range.start}
            colspan={`span ${range.length}`}
            className={`planning--range planning--small is-pw ${
              work.is_provisional ? "is-provisional" : ""
            }`}
            tag="a"
            href={work.url}
            data-toggle="ajaxmodal"
            title={interpolate(gettext("%sh per week"), [fixed(per_week, 1)])}
          >
            <span className="no-pr">{work.text}</span>
          </Cell>
        ))}
    </>
  )
}

function Absences({ absences }) {
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

function UserAbsences({ user }) {
  const ctx = useContext(RowContext)
  const row = ctx.next()

  return (
    <>
      <Cell row={row} column={1} className="planning--title is-absence pl-3">
        {user[0]}
      </Cell>
      {user[1].map((hours, idx) =>
        hours ? (
          <Cell
            key={idx}
            row={row}
            column={FIRST_DATA_COLUMN + idx}
            className="planning--range planning--small is-absence"
          >
            {fixed(hours, 0)}
          </Cell>
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
        ranges.push({ start: rangeStart, length: i - rangeStart })
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

  return ranges
}

const Cell = React.forwardRef(
  (
    {
      row,
      column,
      rowspan = "span 1",
      colspan = "span 1",
      tag = "div",
      children,
      style = {},
      ...props
    },
    ref
  ) =>
    React.createElement(
      tag,
      {
        ref,
        style: {
          gridRow: `${row} / ${rowspan}`,
          gridColumn: `${column} / ${colspan}`,
          ...style,
        },
        ...props,
      },
      children
    )
)
