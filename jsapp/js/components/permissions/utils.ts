import sessionStore from 'js/stores/session';
import permConfig from 'js/components/permissions/permConfig';
import {buildUserUrl, ANON_USERNAME_URL} from 'js/users/utils';
import type {PermissionCodename} from 'js/constants';
import type {
  AssetResponse,
  PermissionResponse,
  ProjectViewAsset,
  SubmissionResponse,
} from 'js/dataInterface';
import {isSelfOwned} from 'jsapp/js/assetUtils';
import type {
  CheckboxNameAll,
  CheckboxNamePartial,
  CheckboxNameListPartial,
} from './permConstants';
import {CHECKBOX_PERM_PAIRS} from './permConstants';

/** For `.find`-ing the permissions */
function _doesPermMatch(
  perm: PermissionResponse,
  permName: PermissionCodename,
  partialPermName: PermissionCodename | null = null
) {
  // Case 1: permissions don't match, stop looking
  if (perm.permission !== permConfig.getPermissionByCodename(permName)?.url) {
    return false;
  }

  // Case 2: permissions match, and we're not looking for partial one
  if (permName !== 'partial_submissions') {
    return true;
  }

  // Case 3a: we are looking for partial permission, but the name was no given
  if (!partialPermName) {
    return false;
  }

  // Case 3b: we are looking for partial permission, check if there are some that match
  return perm.partial_permissions?.some(
    (partialPerm) =>
      partialPerm.url ===
      permConfig.getPermissionByCodename(partialPermName)?.url
  );
}

// NOTE: be aware of the fact that some of non-TypeScript code is passing
// things that are not AssetResponse (probably due to how dmix mixin is used
// - merging asset response directly into component state object)
export function userCan(
  permName: PermissionCodename,
  asset?: AssetResponse | ProjectViewAsset,
  partialPermName: PermissionCodename | null = null
) {
  // Sometimes asset data is not ready yet and we still call the function
  // through some rendering function. We have to be prepared
  if (!asset) {
    return false;
  }

  // TODO: check out whether any other checks are really needed at this point.
  // Pay attention if partial permissions work.
  if ('effective_permissions' in asset) {
    const hasEffectiveAccess = asset.effective_permissions?.some(
      (effectivePerm) => effectivePerm.codename === permName
    );
    if (hasEffectiveAccess) {
      return true;
    }
  }

  const currentUsername = sessionStore.currentAccount.username;

  // If you own the asset, you can do everything with it
  if (asset.owner__username === currentUsername) {
    return true;
  }

  if ('permissions' in asset) {
    // if permission is granted publicly, then grant it to current user
    const anonAccess = asset.permissions.some(
      (perm) =>
        perm.user === ANON_USERNAME_URL &&
        perm.permission === permConfig.getPermissionByCodename(permName)?.url
    );
    if (anonAccess) {
      return true;
    }

    return asset.permissions.some(
      (perm) =>
        perm.user === buildUserUrl(currentUsername) &&
        _doesPermMatch(perm, permName, partialPermName)
    );
  }

  return false;
}

export function userCanPartially(
  permName: PermissionCodename,
  asset?: AssetResponse
) {
  const currentUsername = sessionStore.currentAccount.username;

  // Owners cannot have partial permissions because they have full permissions.
  // Both are contradictory.
  if (asset?.owner__username === currentUsername) {
    return false;
  }

  return userCan('partial_submissions', asset, permName);
}

/**
 * This checks if current user can remove themselves from a project that was
 * shared with them. If `view_asset` comes from `asset.effective_permissions`,
 * but doesn't exist in `asset.permissions` it means that `view_asset` comes
 * from Project View access, not from project being shared with user directly.
 */
export function userCanRemoveSharedProject(asset: AssetResponse) {
  const currentUsername = sessionStore.currentAccount.username;
  const userHasDirectViewAsset = asset.permissions.some(
    (perm) =>
      perm.user === buildUserUrl(currentUsername) &&
      _doesPermMatch(perm, 'view_asset')
  );

  return (
    !isSelfOwned(asset) &&
    userCan('view_asset', asset) &&
    userHasDirectViewAsset
  );
}

/**
 * This implementation does not use the back end to detect if `submission`
 * is writable or not. So far, the front end only supports filters like:
 *    `_submitted_by: {'$in': []}`
 * Let's search for `submissions._submitted_by` value among these `$in`
 * lists.
 */
export function isSubmissionWritable(
  /** Permission to check if user can do at least partially */
  permName: PermissionCodename,
  asset: AssetResponse,
  submission: SubmissionResponse
) {
  // TODO optimize this to avoid calling `userCan()` and `userCanPartially()`
  // repeatedly in the table view
  // TODO Support multiple permissions at once
  const thisUserCan = userCan(permName, asset);
  const thisUserCanPartially = userCanPartially(permName, asset);

  // Case 1: User has full permission
  if (thisUserCan) {
    return true;
  }

  // Case 2: User has neither full nor partial permission
  if (!thisUserCanPartially) {
    return false;
  }

  // Case 3: User has only partial permission, and things are complicated
  const currentUsername = sessionStore.currentAccount.username;
  const partialPerms = asset.permissions.find(
    (perm) =>
      perm.user === buildUserUrl(currentUsername) &&
      _doesPermMatch(perm, 'partial_submissions', permName)
  );

  const partialPerm = partialPerms?.partial_permissions?.find(
    (nestedPerm) =>
      nestedPerm.url === permConfig.getPermissionByCodename(permName)?.url
  );

  const submittedBy = submission._submitted_by;
  // If ther `_submitted_by` was not stored, there is no way of knowing.
  if (submittedBy === null) {
    return false;
  }

  let allowedUsers: string[] = [];

  partialPerm?.filters.forEach((filter) => {
    if (filter._submitted_by) {
      allowedUsers = allowedUsers.concat(filter._submitted_by.$in);
    }
  });
  return allowedUsers.includes(submittedBy);
}

/**
 * For given checkbox name, it returns its partial counterpart (another checkbox
 * name) if it has one.
 */
export function getPartialCheckboxName(
  checkboxName: CheckboxNameAll
): CheckboxNamePartial | undefined {
  switch (checkboxName) {
    case 'submissionsView':
      return 'submissionsViewPartial';
    case 'submissionsEdit':
      return 'submissionsEditPartial';
    case 'submissionsValidate':
      return 'submissionsValidatePartial';
    case 'submissionsDelete':
      return 'submissionsDeletePartial';
    default:
      return undefined;
  }
}

/**
 * Matches given partial checkbox name with the list name
 */
export function getPartialCheckboxListName(
  checkboxName: CheckboxNamePartial
): CheckboxNameListPartial {
  switch (checkboxName) {
    case 'submissionsViewPartial':
      return 'submissionsViewPartialUsers';
    case 'submissionsEditPartial':
      return 'submissionsEditPartialUsers';
    case 'submissionsDeletePartial':
      return 'submissionsDeletePartialUsers';
    case 'submissionsValidatePartial':
      return 'submissionsValidatePartialUsers';
  }
}

/**
 * For given permission name it returns a matching checkbox name (non-partial).
 * It should never return `undefined`, but TypeScript has some limitations.
 */
export function getCheckboxNameByPermission(
  permName: PermissionCodename
): CheckboxNameAll | undefined {
  let found: CheckboxNameAll | undefined;
  for (const [checkboxName, permissionName] of Object.entries(
    CHECKBOX_PERM_PAIRS
  )) {
    // We cast it here because for..of doesn't keep the type of the keys
    const checkboxNameCast = checkboxName as CheckboxNameAll;
    if (permName === permissionName) {
      found = checkboxNameCast;
    }
  }
  return found;
}
