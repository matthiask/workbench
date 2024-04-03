const dayOfWeek = [
  window.pgettext("one letter Sunday", "S"),
  window.pgettext("one letter Monday", "M"),
  window.pgettext("one letter Tuesday", "T"),
  window.pgettext("one letter Wednesday", "W"),
  window.pgettext("one letter Thursday", "T"),
  window.pgettext("one letter Friday", "F"),
  window.pgettext("one letter Saturday", "S"),
]

export function formatDate(d) {
  return `${d.getFullYear()}-${d.getMonth() + 1}-${d.getDate()}`
}

export function readableDate(d) {
  const day = d.getDate()
  const month = d.getMonth() + 1
  const year = d.getFullYear()
  const dow = dayOfWeek[d.getDay()]

  return `${dow} ${day}.${month}.${year}`
}

// https://stackoverflow.com/a/6117889
/* For a given date, get the ISO week number
 *
 * Based on information at:
 *
 *    http://www.merlyn.demon.co.uk/weekcalc.htm#WNR
 *
 * Algorithm is to find nearest thursday, it's year
 * is the year of the week number. Then get weeks
 * between that date and the first day of that year.
 *
 * Note that dates in one year can be weeks of previous
 * or next year, overlap is up to 3 days.
 *
 * e.g. 2014/12/29 is Monday in week  1 of 2015
 *      2012/1/1   is Sunday in week 52 of 2011
 */
export function getWeekNumber(d) {
  // Copy date so don't modify original
  d = new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()))
  // Set to nearest Thursday: current date + 4 - current day number
  // Make Sunday's day number 7
  d.setUTCDate(d.getUTCDate() + 4 - (d.getUTCDay() || 7))
  // Get first day of year
  const yearStart = new Date(Date.UTC(d.getUTCFullYear(), 0, 1))
  // Calculate full weeks to nearest Thursday
  const weekNo = Math.ceil(((d - yearStart) / 86400000 + 1) / 7)
  // Return array of year and week number
  return [d.getUTCFullYear(), weekNo]
}
