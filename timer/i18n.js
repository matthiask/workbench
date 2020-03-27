import React from "react"

const identity = (t) => t
export const gettext = window.gettext || identity

export const OUTCOME = gettext("What outcome do you seek?")
