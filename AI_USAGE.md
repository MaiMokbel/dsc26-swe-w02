Tools
I used ChatGPT and claude to help me understand the requirements, review my API design, and think about possible edge cases. I also used pytest to test the implementation and check whether the API behaved as expected.
What AI got wrong
Some AI suggestions can be too general and may not match the exact requirements of the assignment. For this project, I had to make sure the solutions followed the required API contract, especially the error responses, parcel state transitions, and cursor pagination. I checked these requirements against my code and tests instead of accepting suggestions without verification.
1.Why does listParcels need a cursor rather than an offset?
A cursor remembers where the previous page ended, so the API can continue from that point. This is important when parcels change state between requests, because an offset could skip some parcels or return the same parcel twice.
2.Which of your four operations would break the courier app if you renamed one field, and who would have to approve that change?
Renaming a field in createParcel or recordParcelEvent could break the courier app if it sends that field in a request. The change should be agreed upon by the API/backend team and the courier app team, and the merchant integration team too if the change affects its contract.