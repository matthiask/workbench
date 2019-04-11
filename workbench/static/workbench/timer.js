"use strict";

const {Component, h, render} = window.preact;

function timestamp() {
  return Math.floor(new Date().getTime() / 1000);
}

class App extends Component {
  constructor() {
    super();
    const state = window.localStorage.getItem("workbench-timer");
    if (state) {
      this.state = JSON.parse(state);
    } else {
      this.state = this.defaultState();
    }

    window.addEventListener("storage", e => {
      if (e.key === "workbench-timer") {
        this.setState(JSON.parse(e.newValue));
      }
    });
  }

  componentDidUpdate() {
    window.localStorage.setItem("workbench-timer", JSON.stringify(this.state));

    if (this.state.activeProject) {
      this.ensureUpdates();
    } else {
      this.stopUpdates();
    }
  }

  ensureUpdates() {
    this.stopUpdates();
    this.timer = setInterval(() => this.forceUpdate(), 1000);
  }

  stopUpdates() {
    clearInterval(this.timer);
    this.timer = null;
  }

  defaultState() {
    return {
      projects: [],
      seconds: {},
      activeProject: null,
      lastStart: null
    };
  }

  activateProject(projectId, additionalSecondsState) {
    let seconds = Object.assign({}, this.state.seconds, additionalSecondsState || {});
    if (this.state.activeProject && this.state.lastStart) {
      seconds[this.state.activeProject] =
        (seconds[this.state.activeProject] || 0) +
        timestamp() -
        this.state.lastStart;
    }
    this.setState({
      seconds,
      activeProject: projectId,
      lastStart: projectId === null ? null : timestamp()
    });

    if (projectId && !this.timer) {
      this.ensureUpdates();
    } else if (!projectId) {
      this.stopUpdates();
    }
  }

  render(props, state) {
    window.console && window.console.log(state);
    let content = ["div", {className: ""}];
    if (state.projects) {
      state.projects.forEach(project => {
        const isActiveProject = state.activeProject === project.id;

        let seconds = state.seconds[project.id] || 0;
        if (isActiveProject && state.lastStart) {
          seconds += timestamp() - state.lastStart;
        }
        const hours = Math.ceil(seconds / 360) / 10;

        content.push(
          h(
            Project,
            Object.assign({}, project, {
              hours,
              isActiveProject,
              toggleTimerState: () => {
                if (isActiveProject) {
                  this.activateProject(null);
                } else {
                  this.activateProject(project.id);
                }
              },
              logHours: () => {
                this.activateProject(null, {[project.id]: 0})

                window.openModalFromUrl(
                  `/projects/${project.id}/createhours/?hours=${hours}`
                );
              },
              removeProject: () => {
                this.setState({
                  projects: state.projects.filter(p => p.id !== project.id),
                  seconds: Object.assign({}, state.seconds, {[project.id]: 0})
                });
              }
            })
          )
        );
      });
    }

    content.push(
      h(AddProject, {
        addProject: (id, title) => {
          if (!state.projects.find(p => p.id === id)) {
            let projects = Array.from(state.projects);
            projects.push({id, title});
            projects.sort((a, b) => b.id - a.id);
            this.setState({projects});
          }
        }
      })
    );
    content.push(" ");
    content.push(
      h(
        "button",
        {
          className: "btn btn-sm btn-danger",
          onClick: () => {
            this.setState(this.defaultState());
          }
        },
        "reset"
      )
    );

    return h.apply(null, content);
  }
}

class Project extends Component {
  render(props, _state) {
    return h(
      "div",
      {className: "d-flex justify-content-between my-3"},
      h("a", {href: `/projects/${props.id}/`}, props.title),
      " ",
      h(
        "div",
        null,
        h(
          "button",
          {
            className: `btn btn-sm ${
              props.isActiveProject ? "btn-success" : "btn-outline-secondary"
            }`,
            onClick: () => props.toggleTimerState()
          },
          props.isActiveProject ? "pause" : "start"
        ),
        " ",
        h(
          "button",
          {
            className: "btn btn-outline-secondary btn-sm",
            onClick: () => props.logHours()
          },
          `+${props.hours.toFixed(1)}h`
        ),
        " ",
        h(
          "button",
          {
            className: "btn btn-outline-danger btn-sm",
            onClick: () => props.removeProject()
          },
          "x"
        )
      )
    );
  }
}

class AddProject extends Component {
  render(props, _state) {
    const match = window.location.href.match(/\/projects\/([0-9]+)\//);
    if (!match || !match[1]) return null;

    return h(
      "button",
      {
        className: "btn btn-secondary btn-sm",
        onClick: () =>
          props.addProject(
            parseInt(match[1]),
            document.querySelector("h1").textContent
          )
      },
      "+project"
    );
  }
}

window.addEventListener("load", function() {
  render(h(App), document.querySelector("[data-timer]"));
});
