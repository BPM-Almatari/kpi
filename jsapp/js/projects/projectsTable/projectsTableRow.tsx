import React from 'react';
import {useNavigate} from 'react-router-dom';
import {ROUTES} from 'js/router/routerConstants';
import {PROJECT_FIELDS} from 'js/projects/projectViews/constants';
import type {
  ProjectFieldName,
  ProjectFieldDefinition,
} from 'js/projects/projectViews/constants';
import Badge from 'js/components/common/badge';
import AssetName from 'js/components/common/assetName';
import {formatTime} from 'js/utils';
import type {AssetResponse, ProjectViewAsset} from 'js/dataInterface';
import assetUtils from 'js/assetUtils';
import styles from './projectsTableRow.module.scss';
import classNames from 'classnames';

interface ProjectsTableRowProps {
  asset: AssetResponse | ProjectViewAsset;
  highlightedFields: ProjectFieldName[];
  visibleFields: ProjectFieldName[];
}

export default function ProjectsTableRow(props: ProjectsTableRowProps) {
  const navigate = useNavigate();

  const onRowClick = () => {
    navigate(ROUTES.FORM_SUMMARY.replace(':uid', props.asset.uid));
  };

  const renderColumnContent = (field: ProjectFieldDefinition) => {
    switch (field.name) {
      case 'name':
        return <AssetName asset={props.asset} />;
      case 'description':
        return props.asset.settings.description;
      case 'status':
        if (props.asset.has_deployment && !props.asset.deployment__active) {
          return (
            <Badge
              color='light-amber'
              size='s'
              icon='project-archived'
              label={t('archived')}
            />
          );
        } else if (props.asset.has_deployment) {
          return (
            <Badge
              color='light-blue'
              size='s'
              icon='project-deployed'
              label={t('deployed')}
            />
          );
        } else {
          return (
            <Badge
              color='light-teal'
              size='s'
              icon='project-draft'
              label={t('draft')}
            />
          );
        }
      case 'ownerUsername':
        return assetUtils.getAssetOwnerDisplayName(props.asset.owner__username);
      case 'ownerFullName':
        return 'owner__name' in props.asset ? props.asset.owner__name : null;
      case 'ownerEmail':
        return 'owner__email' in props.asset ? props.asset.owner__email : null;
      case 'ownerOrganization':
        return 'owner__organization' in props.asset
          ? props.asset.owner__organization
          : null;
      case 'dateModified':
        return formatTime(props.asset.date_modified);
      case 'dateDeployed':
        if (
          'date_latest_deployment' in props.asset &&
          props.asset.date_latest_deployment !== null
        ) {
          return formatTime(props.asset.date_latest_deployment);
        }
        return null;
      case 'sector':
        return assetUtils.getSectorDisplayString(props.asset);
      case 'countries':
        if (Array.isArray(props.asset.settings.country)) {
          return props.asset.settings.country.map((country) =>
            <Badge color='cloud' size='m' label={country.label} />
          );
        } else if (typeof props.asset.settings.country === 'string') {
          (<Badge color='cloud' size='m' label={props.asset.settings.country} />);
        }
        return null;
      case 'languages':
        return assetUtils.getLanguagesDisplayString(props.asset);
      case 'submissions':
        return (
          <Badge
            color='cloud'
            size='m'
            label={props.asset.deployment__submission_count}
          />
        );
      default:
        return null;
    }
  };

  return (
    <div
      className={classNames(
        styles.row,
        styles.rowTypeProject
      )}
      onClick={onRowClick}
    >
      {Object.values(PROJECT_FIELDS).map((field: ProjectFieldDefinition) => {
        // Hide not visible fields.
        if (!props.visibleFields.includes(field.name)) {
          return null;
        }

        return (
          <div
            className={classNames({
              [styles.cell]: true,
              [styles.cellHighlighted]: props.highlightedFields.includes(
                field.name
              ),
            })}
            data-fieldName={field.name}
            key={field.name}
          >
            {renderColumnContent(field)}
          </div>
        );
      })}
    </div>
  );
}