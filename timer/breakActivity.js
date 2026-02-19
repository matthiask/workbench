import { useEffect, useRef, useState } from "react"
import Draggable from "react-draggable"
import { connect } from "react-redux"

import { overwriteBreakElapsed, saveBreak } from "./actions.js"
import { ActivitySettings } from "./activitySettings.js"
import { gettext } from "./i18n.js"
import * as icons from "./icons.js"
import { clamp, prettyDuration, timestamp } from "./utils.js"

const createUpdater =
  ({ id, dispatch }) =>
  (fields) =>
    dispatch({ type: "UPDATE_ACTIVITY", id, fields })

export const BreakActivity = connect((state) => ({ current: state.current }))(
  ({ activity, current, dispatch, usedColors }) => {
    const dispatchUpdate = createUpdater({ id: activity.id, dispatch })
    const [showSettings, setShowSettings] = useState(false)
    const [, updateState] = useState()
    const ref = useRef()

    const isRunning = !!activity.startedAt

    // Update clock each second while running
    useEffect(() => {
      if (!isRunning) return
      const interval = setInterval(() => updateState({}), 1000)
      return () => clearInterval(interval)
    }, [isRunning])

    // Auto-save when another activity starts
    const activityRef = useRef(activity)
    activityRef.current = activity
    const mountedRef = useRef(false)
    useEffect(() => {
      if (!mountedRef.current) {
        mountedRef.current = true
        return
      }
      const act = activityRef.current
      if (current?.id && act.startedAt) {
        saveBreak(dispatch, act, { reload: false })
      }
    }, [current?.id, dispatch])

    const elapsed = isRunning ? Math.ceil(timestamp() - activity.startedAt) : 0
    const title = activity.title || gettext("Break")

    return (
      <Draggable
        handle=".js-drag-handle"
        bounds="parent"
        defaultPosition={{
          x:
            10 *
            Math.floor(clamp(activity.left, 0, window.innerWidth - 300) / 10),
          y:
            10 *
            Math.floor(clamp(activity.top, 0, window.innerHeight - 300) / 10),
        }}
        grid={[10, 10]}
        onStop={(_e, data) => dispatchUpdate({ left: data.x, top: data.y })}
        nodeRef={ref}
      >
        <div
          className="activity card px-2 py-2"
          style={{ backgroundColor: activity.color }}
          ref={ref}
        >
          <div className="py-2 px-2 text-truncate js-drag-handle" title={title}>
            {title}
          </div>
          <div className="activity-body">
            <div className="form-group">
              <textarea
                className="form-control"
                rows="2"
                value={activity.description}
                onChange={(e) =>
                  dispatchUpdate({ description: e.target.value })
                }
                placeholder={gettext("Description")}
              />
            </div>
            <div className="d-flex align-items-center justify-content-between">
              {isRunning ? (
                <button
                  type="button"
                  className="activity-duration ps-2"
                  onClick={() => overwriteBreakElapsed(dispatch, activity)}
                  style={{ cursor: "cell" }}
                >
                  {prettyDuration(elapsed)}
                </button>
              ) : (
                <span className="activity-duration ps-2">—</span>
              )}
              <div>
                <button
                  className={`btn btn-light btn-sm ${showSettings ? "active" : ""}`}
                  type="button"
                  onClick={() => setShowSettings(!showSettings)}
                  title={gettext("Settings")}
                >
                  {icons.cog}
                </button>
                {!isRunning && (
                  <button
                    className="btn btn-sm ms-2 btn-light"
                    type="button"
                    onClick={() => {
                      dispatch({ type: "STOP", current })
                      dispatchUpdate({ startedAt: timestamp() })
                    }}
                    title={gettext("Start break")}
                  >
                    {icons.play}
                  </button>
                )}
                <button
                  className="btn btn-sm ms-2 btn-success"
                  type="button"
                  disabled={!isRunning}
                  onClick={() => saveBreak(dispatch, activity)}
                  title={gettext("Save break")}
                >
                  {icons.save}
                </button>
              </div>
            </div>
          </div>
          {showSettings ? (
            <ActivitySettings
              title={activity.title}
              color={activity.color}
              otherColors={usedColors || []}
              dispatchUpdate={dispatchUpdate}
              closeSettings={() => setShowSettings(false)}
              removeActivity={() =>
                dispatch({ type: "REMOVE_ACTIVITY", id: activity.id })
              }
              resetActivity={() => {
                dispatchUpdate({ startedAt: null })
                setShowSettings(false)
              }}
            />
          ) : null}
        </div>
      </Draggable>
    )
  },
)
