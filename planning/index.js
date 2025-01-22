import "./style.scss"

import React, {
  Fragment,
  createContext,
  useContext,
  useLayoutEffect,
  useRef,
  useState,
} from "react"
import { createRoot } from "react-dom/client"

const clamp = (min, value, max) => Math.max(Math.min(value, max), min)
const opacityClamp = (value) => clamp(0.3, value, 1)
const gettext = window.gettext || ((t) => t)
const pgettext = window.pgettext || ((_ctx, t) => t)
const fixed = (s, decimalPlaces) => Number.parseFloat(s).toFixed(decimalPlaces)

document.addEventListener("DOMContentLoaded", () => {
  const data = JSON.parse(document.querySelector("#planning-data").textContent)
  const el = document.querySelector("#planning-root")
  const root = createRoot(el)
  root.render(<Planning data={data} />)

  const style = data.service_types
    .map(
      ({ id, color }) =>
        `.planning--range.st-${id} { --st-color: ${color}; background-color: var(--st-color) !important; }`,
    )
    .join("\n")
  const styleEl = document.createElement("style")
  styleEl.textContent = style
  document.head.appendChild(styleEl)
})

const RowContext = createContext()

const FIRST_DATA_ROW = 3
const FIRST_DATA_COLUMN = 6

function months(weeks) {
  const months = []
  let month = null
  for (let index = 0; index < weeks.length; ++index) {
    const week = weeks[index]
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
    current() {
      return this.__row
    },
    next() {
      return ++this.__row
    },
  }

  const getCollapse = () => {
    const storage = window.localStorage.getItem("planningCollapse")
    return storage ? JSON.parse(storage) : []
  }
  const [collapse, setCollapse] = useState(getCollapse())
  const toggleCollapse = (id) => {
    const storage = window.localStorage.getItem("planningCollapse")
    const storageData = storage ? JSON.parse(storage) : []
    const index = storageData.indexOf(id)
    if (index >= 0) storageData.splice(index, 1)
    else storageData.push(id)
    window.localStorage.setItem("planningCollapse", JSON.stringify(storageData))
    setCollapse(storageData)
  }

  useLayoutEffect(() => {
    gridRef.current.style.setProperty("--rows", rowCtx.current() - 2)
    gridRef.current.style.setProperty(
      "--first-project-row",
      rowCtx.firstProjectRow,
    )

    Array.from(document.querySelectorAll(".planning--title a")).forEach(
      (el) => (el.title = el.textContent),
    )
  }, [collapse])

  return (
    <RowContext.Provider value={rowCtx}>
      <div
        ref={gridRef}
        className={`planning${data.external_view ? " external" : ""}`}
        style={{
          "--weeks": data.weeks.length + 1,
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
        {data.this_week_index === null ? null : (
          <Cell
            key="this_week_index"
            row="1"
            rowspan="-1"
            column={FIRST_DATA_COLUMN + data.this_week_index}
            className="planning--this-week"
          />
        )}
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

        {data.external_view || (
          <>
            <TotalByWeek
              by_week={data.by_week}
              title={gettext("Planned hours per week")}
            />
            <TotalByWeek
              by_week={data.by_week_provisional}
              title={gettext("Of which provisional")}
            />
            {data.capacity && <Capacity {...data.capacity} />}
          </>
        )}

        {data.projects_offers.map((project) => (
          <Project
            key={project.project.id}
            {...project}
            external_view={data.external_view}
            collapse={collapse.includes(project.project.id)}
            toggleCollapse={() => {
              toggleCollapse(project.project.id)
            }}
          />
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
            opacity: opacityClamp(0.3 + Number.parseFloat(hours) / 20),
          }}
        >
          {fixed(hours, 0)}
        </Cell>
      ))}
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
        <strong>{gettext("Remaining capacity per week")}</strong>
      </Cell>
      {total.map((hours, idx) => (
        <Cell
          key={idx}
          row={row}
          column={FIRST_DATA_COLUMN + idx}
          className="planning--range planning--small is-delta"
          style={{
            backgroundColor:
              hours > 0
                ? `hsl(var(--_good), ${clamp(0, hours * 3, 50)}%, 70%)`
                : `hsl(var(--_bad), ${clamp(0, -hours * 5, 70)}%, 70%)`,
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
            backgroundColor:
              hours > 0
                ? `hsl(var(--_good), ${clamp(0, hours * 3, 50)}%, 70%)`
                : `hsl(var(--_bad), ${clamp(0, -hours * 5, 70)}%, 70%)`,
          }}
        >
          {fixed(hours, 0)}
        </Cell>
      ))}
    </>
  )
}

function Project({
  by_week,
  offers,
  project,
  external_view,
  external_work,
  collapse,
  toggleCollapse,
}) {
  const ctx = useContext(RowContext)
  ctx.next() // Skip one row
  const row = ctx.next()
  if (!ctx.firstProjectRow) {
    ctx.firstProjectRow = row
  }

  return (
    <>
      <div
        style={{
          gridRow: `${row} / ${row + (project.worked_hours ? 2 : 1)}`,
          gridColumn: "1 / -1",
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

      {external_view || (
        <Cell
          row={row}
          column={2}
          style={{ color: "var(--primary)" }}
          className="planning--actions no-pr no-wrap"
        >
          <Collapse
            key={project.id}
            name={`planning-collapse-${project.id}`}
            collapse={collapse}
            toggleCollapse={toggleCollapse}
          />{" "}
          <a
            className="planning--add-pw"
            data-ajaxmodal
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
      )}
      <Cell
        row={row}
        column={3}
        className="planning--small text-center"
        style={{ whiteSpace: "nowrap" }}
      >
        {project.range}
      </Cell>
      {external_view || (
        <Cell row={row} column={4} className="planning--small text-right">
          {fixed(project.planned_hours, 0)}h
        </Cell>
      )}
      {external_view ||
        by_week.map((hours, idx) => {
          hours = Number.parseFloat(hours)
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
      {collapse || (
        <>
          {external_view ||
            (project.worked_hours && <WorkedHours project={project} />)}
          {project.milestones ? <Milestones project={project} /> : null}
          {external_work && <ExternalExpenses {...{ external_work }} />}
          {offers?.map((offer, idx) => (
            <Offer key={idx} {...offer} external_view={external_view} />
          ))}
        </>
      )}
    </>
  )
}

function WorkedHours({ project }) {
  const ctx = useContext(RowContext)
  const row = ctx.next()
  const sum = project.worked_hours.reduce((a, b) => a + Number.parseFloat(b), 0)

  return (
    <>
      <Cell row={row} column={1} className="planning--title is-worked no-pr">
        {gettext("Logged hours")}
      </Cell>
      <Cell row={row} column={4} className="planning--small text-right">
        {fixed(sum, 0)}h
      </Cell>

      {project.worked_hours.map((hours, idx) => {
        hours = Number.parseFloat(hours)
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

// function weekdayToGradient(weekday, weekspan) {
//   const width = 8 / weekspan
//   const start =
//     (100 * (weekspan - 1) * 7 + (100 - width) * (weekday - 1)) / (weekspan * 7)
//   const end = start + width
//   return `linear-gradient(to right, transparent ${start}%, rgb(255, 200, 200) ${start}%, rgb(255, 200, 200) ${end}%, transparent ${end}%)`
// }

const weekdayBackgroundPosition = (weekday) => {
  const width = 12
  const start = Math.floor(((100 - width) * (weekday - 1)) / 7)
  return `${start}%`
}

const Milestones = ({ project }) => {
  const ctx = useContext(RowContext)
  const row = ctx.next()
  return (
    <>
      <div
        style={{
          gridRow: row,
          gridColumn: "1 / -1",
        }}
        className="planning--milestones"
      />
      <Cell row={row} column={1} className="planning--title is-milestone pl-3">
        {gettext("milestones")}
      </Cell>
      {project.milestones.map((m, i) => {
        const row = ctx.next()

        const isEven = (1 + i) % 2 === 0

        return (
          <Fragment key={i}>
            {isEven ? (
              <div
                style={{ gridRow: row, gridColumn: "1 / -1" }}
                className="planning--stripe3"
              />
            ) : null}
            <Cell
              row={row}
              column={1}
              className={"planning--title is-pw planning--small pl-5"}
            >
              <a href={m.url} data-ajaxmodal>
                {m.title}
              </a>
            </Cell>
            <Cell
              row={row}
              column={3}
              className={"planning--small text-center is-pr"}
              style={{ whiteSpace: "nowrap" }}
            >
              {m.range}
            </Cell>
            {m.hours > 0 && (
              <Cell
                row={row}
                column={4}
                className={"planning--small text-right is-pr"}
              >
                {`${fixed(m.hours, 0)}h`}
              </Cell>
            )}
            {m.weeks &&
              findContiguousWeekRanges(m.weeks).map((range, idx) => (
                <Cell
                  key={idx}
                  row={row}
                  column={FIRST_DATA_COLUMN + range.start}
                  colspan={`span ${range.length}`}
                  className={"planning--range planning--small is-milestone"}
                  tag="a"
                  href={m.url}
                  data-ajaxmodal
                  title={`${m.title} (${m.dow})`}
                />
              ))}
            {m.graphical_weeks &&
              findContiguousWeekRanges(m.graphical_weeks).map((range, idx) => (
                <Cell
                  key={idx}
                  row={row}
                  column={FIRST_DATA_COLUMN + range.start}
                  colspan={`span ${range.length}`}
                  className={
                    "planning--range planning--small is-milestone-graphic"
                  }
                  style={{
                    left: weekdayBackgroundPosition(m.weekday),
                  }}
                  tag="a"
                  href={m.url}
                  data-ajaxmodal
                  title={`${m.title} (${m.dow})`}
                />
              ))}
          </Fragment>
        )
      })}
    </>
  )
}

function Offer({ offer, external_view, work_list }) {
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
          gridColumn: "1 / -1",
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
      {external_view || (
        <Cell row={row} column={4} className="planning--small text-right">
          {fixed(offer.planned_hours, 0)}h
        </Cell>
      )}
      {work_list.map((work, idx) => (
        <Work key={work.work.id} {...work} isEven={(1 + idx) % 2 === 0} />
      ))}
    </>
  )
}

function Work({ work, hours_per_week, absences, isEven }) {
  const ctx = useContext(RowContext)
  const row = ctx.next()

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
        className={`planning--title is-pw ${
          work.is_provisional ? "is-provisional" : ""
        } planning--small pl-5`}
      >
        <a href={work.url} data-ajaxmodal>
          {work.title}
        </a>
      </Cell>
      {work.is_provisional ? (
        <Cell
          row={row}
          column={2}
          className={"planning--small is-pw"}
          title={gettext("is provisional")}
        >
          {pgettext("provisional", "prov.")}
        </Cell>
      ) : null}
      <Cell
        row={row}
        column={3}
        className={"planning--small text-center is-pr"}
        style={{ whiteSpace: "nowrap" }}
      >
        {work.range}
      </Cell>
      {work.planned_hours > 0 && (
        <Cell
          row={row}
          column={4}
          className={"planning--small text-right is-pr"}
        >
          {`${fixed(work.planned_hours, 0)}h`}
        </Cell>
      )}
      <Cell
        row={row}
        column={5}
        className={"planning--small text-center no-pr"}
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
          data-ajaxmodal
          title={work.tooltip}
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
            } st-${work.service_type_id}`}
            tag="a"
            href={work.url}
            data-ajaxmodal
            title={work.tooltip}
          >
            <span className="no-pr">{work.text}</span>
          </Cell>
        ))}
      {absences.length > 0 &&
        absences.map((absence, idx) => {
          if (absence.length > 0) {
            return (
              <Cell
                key={idx}
                row={row}
                column={FIRST_DATA_COLUMN + idx}
                className="planning--range planning--small is-absence-graphic has-description-popup"
              >
                <AbsencesTooltip absences={absence} />
              </Cell>
            )
          }
        })}
    </>
  )
}

const ExternalExpenses = ({ external_work }) => {
  const ctx = useContext(RowContext)
  const row = ctx.next()
  return (
    <>
      <div
        style={{
          gridRow: row,
          gridColumn: "1 / -1",
        }}
        className="planning--external"
      />
      <Cell row={row} column={1} className="planning--title is-external pl-3">
        {gettext("Efforts")}
      </Cell>
      {external_work.map((work, idx) => (
        <ExternalWork key={idx} idx={idx} work={work} />
      ))}
    </>
  )
}

const ExternalWork = ({ idx, work }) => {
  const ctx = useContext(RowContext)
  const row = ctx.next()

  const isEven = (1 + idx) % 2 === 0

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
        className={`planning--title is-pw ${
          work.is_provisional ? "is-provisional" : ""
        } planning--small pl-5`}
      >
        <a href={work.url} data-ajaxmodal>
          {work.title} ({work.provided_by})
        </a>
      </Cell>
      <Cell
        row={row}
        column={3}
        className={"planning--small text-center is-pr"}
        style={{ whiteSpace: "nowrap" }}
      >
        {work.range}
      </Cell>
      {work.by_week &&
        findContiguousWeekRanges(work.by_week).map((range, idx) => (
          <Cell
            key={idx}
            row={row}
            column={FIRST_DATA_COLUMN + range.start}
            colspan={`span ${range.length}`}
            className={`planning--range planning--small is-pw st-${work.service_type_id}`}
            tag="a"
            href={work.url}
            data-ajaxmodal
            title={work.tooltip}
          />
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
          gridColumn: "1 / -1",
        }}
        className="planning--stripe1"
      />
      <Cell row={row} column={1} className="planning--title is-project">
        <strong>{gettext("Absences and public holidays")}</strong>
      </Cell>
      {absences.map((user, idx) => (
        <UserAbsences key={idx} user={user} />
      ))}
    </>
  )
}

// function ProjectAbsences({ absences }) {
//   const ctx = useContext(RowContext)
//   const row = ctx.next()
//   return (
//     <>
//       <div
//         style={{
//           gridRow: row,
//           gridColumn: `1 / -1`,
//         }}
//         className="planning--absences"
//       />
//       <Cell row={row} column={1} className="planning--title is-project-absence">
//         {gettext("Concurrent absences")}
//       </Cell>
//       {absences.map((user, idx) => (
//         <ProjectUserAbsence key={idx} user={user} />
//       ))}
//     </>
//   )
// }

// function ProjectUserAbsence({ user }) {
//   const ctx = useContext(RowContext)
//   const row = ctx.next()

//   const userAbsences = user[1].map(
//     (hours) => (hours[0] && hours[0][0]) || "0.0"
//   )

//   return (
//     <>
//       <Cell
//         row={row}
//         column={1}
//         className="planning--small is-project-absence pl-3"
//       >
//         {user[0].name}
//       </Cell>
//       <Cell
//         row={row}
//         column={5}
//         className={`planning--small text-center no-pr`}
//       >
//         {user[0].short_name}
//       </Cell>
//       {findContiguousWeekRanges(userAbsences).map((range, idx) => {
//         return (
//           <Cell
//             key={idx}
//             row={row}
//             column={FIRST_DATA_COLUMN + range.start}
//             colspan={`span ${range.length}`}
//             className={`planning--range planning--small is-project-absence`}
//           >
//             <span className="no-pr">{user[0].short_name}</span>
//           </Cell>
//         )
//       })}
//     </>
//   )
// }

const AbsencesTooltip = ({ absences }) => {
  return (
    <div className="description-popup no-pr">
      {absences.map(([hours, description, url], idx) => (
        <p key={idx}>
          {url ? (
            <a key={url} href={url} data-ajaxmodal>
              {fixed(hours, 0)}h: {description}
            </a>
          ) : (
            `${fixed(hours, 0)}h: ${description}`
          )}
        </p>
      ))}
    </div>
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
      {user[1].map((absences, idx) => {
        if (!absences.length) return null

        const hours = absences.reduce((a, b) => a + Number.parseFloat(b[0]), 0)

        return (
          <Cell
            key={idx}
            row={row}
            column={FIRST_DATA_COLUMN + idx}
            className="planning--range planning--small is-absence has-description-popup"
          >
            {fixed(hours, 0)}
            <AbsencesTooltip {...{ absences }} />
          </Cell>
        )
      })}
    </>
  )
}

function findContiguousWeekRanges(hours_per_week) {
  hours_per_week = hours_per_week.map((hours) => Number.parseFloat(hours))

  let rangeStart = -1
  // const ranges = [{start: 0, length: hours_per_week.length - 1}]
  // return ranges

  const ranges = []

  for (let i = 0; i < hours_per_week.length; ++i) {
    if (hours_per_week[i]) {
      if (rangeStart < 0) {
        // Start new range
        rangeStart = i
      }
    } else if (rangeStart >= 0) {
      ranges.push({ start: rangeStart, length: i - rangeStart })
      rangeStart = -1
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
    ref,
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
      children,
    ),
)

const Collapse = ({ name, collapse, toggleCollapse }) => {
  return (
    <>
      <input
        type="checkbox"
        id={name}
        checked={collapse}
        onChange={() => {
          toggleCollapse()
        }}
        className="planning--collapse__input"
      />
      <label for={name}>
        {collapse ? (
          <svg
            class="planning--collapse__icon"
            focusable="false"
            aria-hidden="true"
            viewBox="0 0 24 24"
          >
            <path d="m7 10 5 5 5-5z" />
          </svg>
        ) : (
          <svg
            class="planning--collapse__icon"
            focusable="false"
            aria-hidden="true"
            viewBox="0 0 24 24"
          >
            <path d="m7 14 5-5 5 5z" />
          </svg>
        )}
      </label>
    </>
  )
}
