Status
Accepted
Context
The parcel API needs to control which state changes are allowed. For example, a parcel can be dispatched and then delivered, but a parcel that is already delivered should not accept a failure event. Keeping these rules inside the API endpoints would make the code harder to test and maintain.
Decision
The parcel lifecycle rules are implemented in the separate app.domain module using apply_event(). The function uses a transition table, returns a new immutable Parcel, and raises InvalidTransition when an event is not allowed. The API handles the HTTP response when a transition fails.
Consequences
The lifecycle rules can be tested independently of FastAPI, and the parcel is not replaced in the API's store when a transition fails. However, changes to the lifecycle rules must be reflected in the domain tests and any API behavior that depends on them.