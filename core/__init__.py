"""The metrics core: everything that turns the export into a number.

Nothing in here imports Streamlit, and nothing imports pandas. The whole
package runs under a bare interpreter in about a second, which is what keeps
the correctness path testable independently of the app that renders it.

Import order runs one way only: prep -> metrics -> tools -> llm. `provenance`
sits to the side and depends on nothing but the standard library.
"""
