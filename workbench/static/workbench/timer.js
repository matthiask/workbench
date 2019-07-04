import {Component, render, html} from "/static/workbench/lib/preact-htm.min.js"

function timestamp() {
  return Math.floor(new Date().getTime() / 1000)
}

function prettyDuration(seconds) {
  const hours = Math.floor(seconds / 3600)
  const displayHours = hours ? `${hours}h ` : ""
  const displayMinutes = Math.floor(seconds / 60) % 60
  const displaySeconds = (seconds % 60).toString().padStart(2, "0")
  return `+${displayHours}${displayMinutes}:${displaySeconds}`
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

    this.serialize = this.serialize.bind(this)
  }

  serialize() {
    window.localStorage.setItem("workbench-timer", JSON.stringify(this.state))
  }

  defaultState() {
    return {
      projects: [],
      seconds: {},
      activeProject: null,
      lastStart: null,
    }
  }

  activateProject(projectId, callback) {
    this.setState(
      prevState => {
        let seconds = Object.assign({}, prevState.seconds)
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
      },
      () => {
        callback && callback()
        this.serialize()
      }
    )
  }

  render(props, state) {
    let content = []
    if (state.projects.length) {
      content = content.concat(
        state.projects.map(project => {
          const isActiveProject = state.activeProject === project.id
          return html`
            <${Project}
              project=${project}
              isActiveProject=${isActiveProject}
              lastStart=${isActiveProject ? state.lastStart : null}
              seconds=${state.seconds[project.id] || 0}
              target=${this.props.standalone ? "_blank" : ""}
              toggleTimerState=${() => {
                if (isActiveProject) {
                  this.activateProject(null)
                } else {
                  this.activateProject(project.id)
                }
              }}
              logHours=${() => {
                this.activateProject(null, () => {
                  const seconds = this.state.seconds[project.id] || 0
                  const hoursParam =
                    seconds > 0 ? `?hours=${Math.ceil(seconds / 360) / 10}` : ""

                  window.openModalFromUrl(
                    `/projects/${project.id}/createhours/${hoursParam}`
                  )
                })
              }}
              resetHours=${() => {
                this.setState(
                  prevState => ({
                    seconds: Object.assign({}, prevState.seconds, {
                      [project.id]: 0,
                    }),
                    lastStart:
                      prevState.activeProject === project.id
                        ? timestamp()
                        : prevState.lastStart,
                  }),
                  this.serialize
                )
              }}
              removeProject=${() => {
                if (confirm("Wirklich entfernen?")) {
                  let seconds = Object.assign({}, state.seconds)
                  delete seconds[project.id]
                  this.setState(
                    prevState => ({
                      seconds,
                      projects: prevState.projects.filter(
                        p => p.id !== project.id
                      ),
                      activeProject:
                        prevState.activeProject === project.id
                          ? null
                          : prevState.activeProject,
                      lastStart:
                        prevState.activeProject === project.id
                          ? null
                          : prevState.lastStart,
                    }),
                    this.serialize
                  )
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
                  }, this.serialize)
                }
              }}
            />
            ${" "}
            <${Reset}
              reset=${() => {
                if (confirm("Wirklich zurücksetzen?")) {
                  this.setState(this.defaultState(), this.serialize)
                }
              }}
            />
          </div>
        </div>
        <div class="timer-panel-projects list-group">${content}</div>
      </div>
    `
  }
}

class Project extends Component {
  updateHoursButton() {
    if (!this.hoursButton) return

    const seconds =
      this.props.seconds +
      (this.props.isActiveProject ? timestamp() - this.props.lastStart : 0)
    const deciHours = Math.ceil(seconds / 360) / 10

    this.hoursButton.textContent = prettyDuration(seconds)
    this.hoursButton.title = `${deciHours}h aufschreiben`
  }

  render(props) {
    setTimeout(this.updateHoursButton.bind(this), 0)

    if (props.isActiveProject) {
      this.timer = setInterval(this.updateHoursButton.bind(this), 1000)
    } else if (this.timer) {
      clearInterval(this.timer)
      this.timer = null
    }

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
          <span ref=${button => (this.hoursButton = button)}></span>
          ${" "}
          <button
            class=${`btn btn-sm ${
              props.isActiveProject ? "btn-success" : "btn-outline-secondary"
            }`}
            onClick=${() => props.toggleTimerState()}
            title=${props.isActiveProject ? "Timer stoppen" : "Timer starten"}
          >
            ${props.isActiveProject ? "stop" : "start"}
          </button>
          ${" "}
          <button
            class="btn btn-outline-secondary btn-sm"
            onClick=${() => props.logHours()}
            title="Stunden erfassen"
          >
            log
          </button>
          ${" "}
          <button
            class="btn btn-outline-secondary btn-sm"
            onClick=${() => props.resetHours()}
            title="Timer zurücksetzen"
          >
            reset
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
          document.querySelector("h1").dataset.timerTitle
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
    "innerHeight=750,innerWidth=650,resizable=yes,scrollbars=yes,alwaysOnTop=yes,location=no,menubar=no,toolbar=no"
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

    if (timer.dataset.timer == "footer" && window.hoverintent) {
      window
        .hoverintent(
          timer,
          () => timer.classList.add("hover-with-intent"),
          () => timer.classList.remove("hover-with-intent")
        )
        .options({timeout: 50})
    }
  }
})
