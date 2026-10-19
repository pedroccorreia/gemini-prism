#!/bin/bash
set -euo pipefail

# Prompt or load configuration for bootstrap project
if [ -z "${BOOTSTRAP_PROJECT:-}" ]; then
  read -r -p "Enter GCP Bootstrap Project ID: " BOOTSTRAP_PROJECT
fi

SA_NAME="gemini-provisioner"
SA_EMAIL="${SA_NAME}@${BOOTSTRAP_PROJECT}.iam.gserviceaccount.com"

echo "=== Stage 1: Creating Provisioner Service Account in ${BOOTSTRAP_PROJECT} ==="
if ! gcloud iam service-accounts describe "${SA_EMAIL}" --project "${BOOTSTRAP_PROJECT}" &>/dev/null; then
  gcloud iam service-accounts create "${SA_NAME}" \
    --display-name="Prism — Gemini IaC Provisioner" \
    --project "${BOOTSTRAP_PROJECT}"
  echo "Service account created: ${SA_EMAIL}"
else
  echo "Service account already exists: ${SA_EMAIL}"
fi

echo "=== Stage 2: Granting Service Account Token Creator to Active User ==="
ACTIVE_USER=$(gcloud config get-value account 2>/dev/null || echo "")
if [ -n "${ACTIVE_USER}" ]; then
  echo "Granting roles/iam.serviceAccountTokenCreator on ${SA_EMAIL} to ${ACTIVE_USER}..."
  gcloud iam service-accounts add-iam-policy-binding "${SA_EMAIL}" \
    --member="user:${ACTIVE_USER}" \
    --role="roles/iam.serviceAccountTokenCreator" \
    --project "${BOOTSTRAP_PROJECT}" --quiet
fi

echo ""
echo "=========================================================================="
echo " Stage 1 Foundation: Terraform Init & Apply"
echo "=========================================================================="
echo "Initial foundation provisioning creates projects, APIs, Cloud Identity groups,"
echo "service agent identities, and user stores (with connectors disabled)."
echo "=========================================================================="
echo ""

terraform init
terraform apply -var="sa_email=${SA_EMAIL}" -var="billing_project=${BOOTSTRAP_PROJECT}"

echo ""
echo "=========================================================================="
echo " NEXT STEPS: Workspace Admin Domain-Wide Delegation (DWD)"
echo "=========================================================================="
echo "1. Run the following command to retrieve the DWD authorization checklist:"
echo "   terraform output dwd_checklist"
echo "2. Authorize each environment's Discovery Engine service agent in the Admin Console:"
echo "   https://admin.google.com/ac/owl/domainwidedelegation"
echo "3. After authorization, deploy Workspace connectors & Gemini Enterprise apps:"
echo "   terraform apply -var=\"enable_connectors=true\""
echo "4. Distribute seat licenses to projects:"
echo "   python3 scripts/allocate_licenses.py --distribute"
echo "5. Verify the deployment:"
echo "   python3 scripts/verify.py"
echo "=========================================================================="
