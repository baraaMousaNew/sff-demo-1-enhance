transactions = {
    "Person.Register": "4",
    "Claim.Submission": "2",
    "Remittance.Advice":"8",
    "Prior.Request":"16",
    "Prior.Authorization":"32",
    "Cost.Submission":"64"
}

def get_transaction_from_request(request):
    return transactions[request]