#!/bin/bash
# Checkmk local check: Git repo health (dirty + ahead/behind vs origin)
# Place it in: /usr/lib/check_mk_agent/local/ or /usr/lib/check_mk_agent/local/<interval>/
# Needs: git + rights to read repo as ANSIBLE_USER

REPO="/home/ansible/ansible-project"
SERVICE_NAME="git_repo_health"
ANSIBLE_USER="ansible"
GIT="/usr/bin/git"
REMOTE_NAME="origin"
BRANCH=""   # leave empty to auto-detect current branch (recommended)

run_git() {
  su -s /bin/bash "$ANSIBLE_USER" -c "$GIT -C '$REPO' $*"
}

# Repo exists?
if [ ! -d "$REPO/.git" ]; then
  echo "3 $SERVICE_NAME - CRIT: repo introuvable ($REPO)"
  exit 0
fi

# Detect branch if not set
if [ -z "$BRANCH" ]; then
  BRANCH=$(run_git "rev-parse --abbrev-ref HEAD" 2>/dev/null)
  if [ -z "$BRANCH" ] || [ "$BRANCH" = "HEAD" ]; then
    echo "3 $SERVICE_NAME - CRIT: impossible de détecter la branche"
    exit 0
  fi
fi

# Ensure remote exists
REMOTE_URL=$(run_git "remote get-url $REMOTE_NAME" 2>/dev/null)
if [ -z "$REMOTE_URL" ]; then
  echo "3 $SERVICE_NAME - CRIT: remote '$REMOTE_NAME' absent"
  exit 0
fi

# Dirty working tree?
DIRTY=$(run_git "status --porcelain" 2>/dev/null)
DIRTY_COUNT=0
if [ -n "$DIRTY" ]; then
  DIRTY_COUNT=$(echo "$DIRTY" | wc -l)
fi

# Fetch remote refs (quiet)
FETCH_ERR=$(run_git "fetch --quiet $REMOTE_NAME" 2>&1)
if [ $? -ne 0 ]; then
  echo "2 $SERVICE_NAME - CRIT: fetch KO ($FETCH_ERR)"
  exit 0
fi

# Ensure upstream ref exists locally after fetch
UPSTREAM_REF="$REMOTE_NAME/$BRANCH"
run_git "rev-parse --verify --quiet $UPSTREAM_REF" >/dev/null 2>&1
if [ $? -ne 0 ]; then
  echo "2 $SERVICE_NAME - CRIT: upstream absent ($UPSTREAM_REF)"
  exit 0
fi

# Ahead/Behind
AHEAD=$(run_git "rev-list --count $UPSTREAM_REF..$BRANCH" 2>/dev/null)
BEHIND=$(run_git "rev-list --count $BRANCH..$UPSTREAM_REF" 2>/dev/null)

# Safety defaults
AHEAD=${AHEAD:-0}
BEHIND=${BEHIND:-0}

# Compose status
# Priority: CRIT for diverged? (I keep WARN) + CRIT for fetch/upstream issues already handled
STATE=0
MSG="OK: clean et synchro"
DETAILS="branch=$BRANCH remote=$REMOTE_NAME"

if [ "$DIRTY_COUNT" -gt 0 ]; then
  STATE=1
  MSG="WARN: $DIRTY_COUNT fichier(s) modifié(s)/non tracké(s) non commit"
fi

if [ "$AHEAD" -gt 0 ] && [ "$BEHIND" -gt 0 ]; then
  STATE=1
  MSG="WARN: divergé (ahead=$AHEAD / behind=$BEHIND)"
elif [ "$AHEAD" -gt 0 ]; then
  STATE=1
  MSG="WARN: $AHEAD commit(s) non pushé(s)"
elif [ "$BEHIND" -gt 0 ]; then
  STATE=1
  MSG="WARN: $BEHIND commit(s) en retard (pull/fetch needed)"
fi

# If both dirty and sync issue, enrich message
if [ "$DIRTY_COUNT" -gt 0 ] && { [ "$AHEAD" -gt 0 ] || [ "$BEHIND" -gt 0 ]; }; then
  MSG="WARN: dirty=$DIRTY_COUNT, ahead=$AHEAD, behind=$BEHIND"
  STATE=1
fi

echo "$STATE $SERVICE_NAME - $MSG | dirty=$DIRTY_COUNT;1;5;0; ahead=$AHEAD;1;5;0; behind=$BEHIND;1;5;0; $DETAILS"
exit 0
