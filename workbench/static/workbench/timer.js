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
    this.timer = setInterval(() => this.forceUpdate(), 10000);
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
    this.setState(function(prevState) {
      let seconds = Object.assign(
        {},
        prevState.seconds,
        additionalSecondsState || {}
      );
      if (prevState.activeProject && prevState.lastStart) {
        seconds[prevState.activeProject] =
          (seconds[prevState.activeProject] || 0) +
          timestamp() -
          prevState.lastStart;
      }
      return {
        seconds,
        activeProject: projectId,
        lastStart: projectId === null ? null : timestamp() - 1
      };
    });

    if (projectId && !this.timer) {
      this.ensureUpdates();
    } else if (!projectId) {
      this.stopUpdates();
    }
  }

  render(props, state) {
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
          h(Project, {
            project,
            hours,
            isActiveProject,
            target: this.props.standalone ? "_blank" : "",
            toggleTimerState: () => {
              if (isActiveProject) {
                this.activateProject(null);
              } else {
                this.activateProject(project.id);
              }
            },
            logHours: () => {
              this.activateProject(null, {[project.id]: 0});

              window.openModalFromUrl(
                `/projects/${project.id}/createhours/?hours=${hours}`
              );
            },
            removeProject: () => {
              let seconds = Object.assign({}, state.seconds);
              delete seconds[project.id];
              this.setState({
                seconds,
                projects: state.projects.filter(p => p.id !== project.id)
              });
            }
          })
        );
      });
    }

    if (!this.props.standalone) {
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
        h(Reset, {
          reset: () => {
            this.setState(this.defaultState());
          }
        })
      );
      content.push(" ");
      content.push(h(StandAlone));
    }

    return h(
      "div",
      {className: "timer-panel"},
      h(
        "div",
        {className: "bg-info text-light timer-panel-tab px-4 py-2"},
        "Timer"
      ),
      h("div", {className: "px-4 pb-4"}, h.apply(null, content))
    );
  }
}

function Project(props) {
  return h(
    "div",
    {className: "my-3"},
    h(
      "a",
      {
        className: "d-block text-truncate",
        href: `/projects/${props.project.id}/`,
        target: props.target
      },
      props.project.title
    ),
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
          onClick: () => props.toggleTimerState(),
          title: props.isActiveProject ? "Pause work" : "Resume work"
        },
        props.isActiveProject ? "pause" : "start"
      ),
      " ",
      h(
        "button",
        {
          className: "btn btn-outline-secondary btn-sm",
          onClick: () => props.logHours(),
          title: "Log hours"
        },
        `+${props.hours.toFixed(1)}h`
      ),
      " ",
      h(
        "button",
        {
          className: "btn btn-outline-danger btn-sm",
          onClick: () => props.removeProject(),
          title: "Remove project"
        },
        "x"
      )
    )
  );
}

function AddProject(props) {
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

function Reset(props) {
  return h(
    "button",
    {
      className: "btn btn-sm btn-danger",
      onClick: () => props.reset()
    },
    "reset"
  );
}

function StandAlone() {
  return h(
    "button",
    {
      className: "btn btn-sm btn-info",
      onClick: () => {
        window.open(
          "/timer/",
          "timer",
          "innerHeight=550,innerWidth=500,resizable=yes,scrollbars=yes,alwaysOnTop=yes,location=no,menubar=no,toolbar=no"
        );
      }
    },
    "window"
  );
}

window.addEventListener("load", function() {
  let timer = document.querySelector("[data-timer]");
  if (timer) {
    render(h(App, {standalone: timer.dataset.timer == "standalone"}), timer);
  }
});
