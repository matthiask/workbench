import {Component, render, html} from "/static/workbench/lib/preact-htm.min.js"

function timestamp() {
  return Math.floor(new Date().getTime() / 1000)
}

class App extends Component {
  constructor() {
    super()
    const state = window.localStorage.getItem("workbench-timer")
    if (state) {
      this.state = JSON.parse(state)
    } else {
      this.state = this.defaultState()
    }

    window.addEventListener("storage", e => {
      if (e.key === "workbench-timer") {
        this.setState(JSON.parse(e.newValue))
      }
    })
  }

  ensureUpdatesIfActive() {
    if (this.state.activeProject) {
      this.ensureUpdates()
    } else {
      this.stopUpdates()
    }
  }

  componentDidMount() {
    this.ensureUpdatesIfActive()
  }

  componentDidUpdate() {
    window.localStorage.setItem("workbench-timer", JSON.stringify(this.state))
    this.ensureUpdatesIfActive()
  }

  ensureUpdates() {
    this.stopUpdates()
    this.timer = setInterval(() => this.forceUpdate(), 1000)
  }

  stopUpdates() {
    clearInterval(this.timer)
    this.timer = null
  }

  defaultState() {
    return {
      projects: [],
      seconds: {},
      activeProject: null,
      lastStart: null,
    }
  }

  activateProject(projectId, additionalSecondsState) {
    this.setState(prevState => {
      let seconds = Object.assign(
        {},
        prevState.seconds,
        additionalSecondsState || {}
      )
      if (prevState.activeProject && prevState.lastStart) {
        seconds[prevState.activeProject] =
          (seconds[prevState.activeProject] || 0) +
          timestamp() -
          prevState.lastStart
      }
      return {
        seconds,
        activeProject: projectId,
        lastStart: projectId === null ? null : timestamp() - 1,
      }
    })

    if (projectId && !this.timer) {
      this.ensureUpdates()
    } else if (!projectId) {
      this.stopUpdates()
    }
  }

  render(props, state) {
    window.console && window.console.log("RENDERING", new Date())
    let content = []
    if (state.projects.length) {
      content = content.concat(
        state.projects.map(project => {
          const isActiveProject = state.activeProject === project.id

          let seconds = state.seconds[project.id] || 0
          if (isActiveProject && state.lastStart) {
            seconds += timestamp() - state.lastStart
          }

          const deciHours = Math.ceil(seconds / 360) / 10
          const minutes = Math.floor(seconds / 60)
          const displayHours =
            minutes >= 60 ? `${Math.floor(minutes / 60)}h ` : ""
          const displayMinutes = minutes % 60
          const displaySeconds = (seconds % 60).toString().padStart(2, "0")

          return html`
            <${Project}
              project=${project}
              deciHours=${deciHours}
              elapsed=${`${displayHours}${displayMinutes}:${displaySeconds}`}
              isActiveProject=${isActiveProject}
              target=${this.props.standalone ? "_blank" : ""}
              toggleTimerState=${() => {
                if (isActiveProject) {
                  this.activateProject(null)
                } else {
                  this.activateProject(project.id)
                }
              }}
              logHours=${() => {
                this.activateProject(null, {[project.id]: 0})

                window.openModalFromUrl(
                  `/projects/${project.id}/createhours/?hours=${deciHours}`
                )
              }}
              removeProject=${() => {
                if (confirm("Wirklich entfernen?")) {
                  let seconds = Object.assign({}, state.seconds)
                  delete seconds[project.id]
                  this.setState(prevState => ({
                    seconds,
                    projects: prevState.projects.filter(
                      p => p.id !== project.id
                    ),
                  }))
                }
              }}
            />
          `
        })
      )
    } else {
      content.push(
        html`
          <div
            class="list-group-item d-flex align-items-center justify-content-center"
          >
            Noch keine Projekte hinzugefügt.
          </div>
        `
      )
    }

    return html`
      <div class="timer-panel">
        <div
          class="timer-panel-tab bg-info text-light px-4 py-2 d-flex align-items-center justify-content-between"
        >
          Timer
          <div class=${this.props.standalone && "d-none"}>
            <${StandAlone} />
            ${" "}
            <${AddProject}
              addProject=${(id, title) => {
                if (!state.projects.find(p => p.id === id)) {
                  this.setState(prevState => {
                    let projects = Array.from(prevState.projects)
                    projects.push({id, title})
                    projects.sort((a, b) => b.id - a.id)
                    return {
                      projects,
                      seconds: Object.assign({}, prevState.seconds, {[id]: 0}),
                    }
                  })
                }
              }}
            />
            ${" "}
            <${Reset}
              reset=${() => {
                if (confirm("Wirklich zurücksetzen?")) {
                  this.setState(this.defaultState())
                }
              }}
            />
          </div>
        </div>
        <div class="list-group">${content}</div>
      </div>
    `
  }
}

function Project(props) {
  return html`
    <div
      class="list-group-item d-flex align-items-center justify-content-between"
    >
      <a
        class="d-block text-truncate"
        href=${`/projects/${props.project.id}/`}
        target=${props.target}
      >
        ${props.project.title}
      </a>

      <div class="text-nowrap">
        <button
          class=${`btn btn-sm ${
            props.isActiveProject ? "btn-success" : "btn-outline-secondary"
          }`}
          onClick=${() => props.toggleTimerState()}
          title=${props.isActiveProject ? "Timer stoppen" : "Timer starten"}
        >
          ${props.isActiveProject ? "pause" : "start"}
        </button>
        ${" "}
        <button
          class="btn btn-outline-secondary btn-sm"
          onClick=${() => props.logHours()}
          title=${`${props.deciHours}h aufschreiben`}
        >
          +${props.elapsed}
        </button>
        ${" "}
        <button
          class="btn btn-outline-danger btn-sm"
          onClick=${() => props.removeProject()}
          title="Projekt entfernen"
        >
          x
        </button>
      </div>
    </div>
  `
}

function AddProject(props) {
  const match = window.location.href.match(/\/projects\/([0-9]+)\//)
  if (!match || !match[1]) return null

  return html`
    <button
      class="btn btn-secondary btn-sm"
      onClick=${() =>
        props.addProject(
          parseInt(match[1]),
          document.querySelector("h1").textContent
        )}
    >
      +Projekt
    </button>
  `
}

function Reset(props) {
  return html`
    <button class="btn btn-sm btn-danger" onClick=${() => props.reset()}>
      Reset
    </button>
  `
}

function openPopup() {
  window.open(
    "/timer/",
    "timer",
    "innerHeight=550,innerWidth=500,resizable=yes,scrollbars=yes,alwaysOnTop=yes,location=no,menubar=no,toolbar=no"
  )
}

function StandAlone() {
  return html`
    <button class="btn btn-sm btn-secondary" onClick=${openPopup}>
      In Popup öffnen
    </button>
  `
}

window.addEventListener("load", function() {
  let timer = document.querySelector("[data-timer]")
  if (timer) {
    render(
      html`
        <${App} standalone=${timer.dataset.timer == "standalone"} />
      `,
      timer
    )
  }
})
