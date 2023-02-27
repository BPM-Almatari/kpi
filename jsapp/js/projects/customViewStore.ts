import $ from 'jquery';
import {makeAutoObservable} from 'mobx';
import type {
  ProjectViewAsset,
  PaginatedResponse,
  FailResponse,
} from 'js/dataInterface';
import {handleApiFail} from 'js/utils';
import {DEFAULT_PROJECT_FIELDS, PROJECT_FIELDS} from './projectViews/constants';
import type {
  ProjectFieldName,
  ProjectsFilterDefinition,
} from './projectViews/constants';
import {buildQueriesFromFilters} from './projectViews/utils';
import type {ProjectsTableOrder} from './projectsTable/projectsTable';
import session from 'js/stores/session';
import {ROOT_URL} from 'js/constants';
import type {EnvStoreFieldItem} from 'js/envStore';
import envStore from 'js/envStore';

const SAVE_DATA_NAME = 'project_views_settings';
const PAGE_SIZE = 50;

const DEFAULT_VIEW_SETTINGS: ViewSettings = {
  filters: [],
  order: {
    fieldName: PROJECT_FIELDS.name.name,
    direction: 'ascending',
  },
  // When fields are `undefined`, it means the deafult fields (from
  // `DEFAULT_PROJECT_FIELDS`) are being used.
  fields: undefined,
};

/** Settings of a different views to be stored on backend. */
export interface ProjectViewsSettings {
  [viewUid: string]: ViewSettings;
}

interface ViewSettings {
  filters: ProjectsFilterDefinition[];
  order: ProjectsTableOrder;
  fields?: ProjectFieldName[];
}

class CustomViewStore {
  public assets: ProjectViewAsset[] = [];
  public filters: ProjectsFilterDefinition[] = DEFAULT_VIEW_SETTINGS.filters;
  public order: ProjectsTableOrder = DEFAULT_VIEW_SETTINGS.order;
  public fields?: ProjectFieldName[] = DEFAULT_VIEW_SETTINGS.fields;
  /** Whether the first call was made. */
  public isFirstLoadComplete = false;
  public isLoading = false;
  private viewUid?: string;
  /** We use `null` here because the endpoint uses it. */
  private nextPageUrl: string | null = null;
  private ongoingFetch?: JQuery.jqXHR;

  constructor() {
    makeAutoObservable(this);
  }

  /** Use this whenever you need to change the view */
  public setUp(viewUid: string) {
    this.viewUid = viewUid;
    this.assets = [];
    this.isFirstLoadComplete = false;
    this.isLoading = false;
    this.nextPageUrl = null;
    this.loadSettings();
  }

  /** If next page of results is available. */
  public get hasMoreAssets(): boolean {
    return this.nextPageUrl !== null;
  }

  /** Stores the new filters and fetches completely new list of assets. */
  public setFilters(filters: ProjectsFilterDefinition[]) {
    this.filters = filters;
    this.saveSettings();
    this.fetchAssets();
  }

  /** Stores the new ordering and fetches completely new list of assets. */
  public setOrder(order: ProjectsTableOrder) {
    this.order = order;
    this.saveSettings();
    this.fetchAssets();
  }

  public setFields(fields: ProjectFieldName[] | undefined) {
    this.fields = fields;
    this.saveSettings();
    // NOTE: we don't need to fetch assets again, fields are UI only
  }

  public hideField(fieldName: ProjectFieldName) {
    let newFields = Array.isArray(this.fields)
      ? Array.from(this.fields)
      : DEFAULT_PROJECT_FIELDS;
    newFields = newFields.filter((item) => item !== fieldName);
    this.setFields(newFields);
  }

  /**
   * Returns an ordering value for current order property. Olivier said it best:
   * > `-name` is descending and `name` is ascending
   */
  private getOrderQuery() {
    const fieldDefinition = PROJECT_FIELDS[this.order.fieldName];
    if (this.order.direction === 'descending') {
      return `-${fieldDefinition.apiOrderingName}`;
    }
    return fieldDefinition.apiOrderingName;
  }

  /**
   * Gets the first page of results. It will replace whatever assets are loaded
   * already.
   */
  public fetchAssets() {
    this.isFirstLoadComplete = false;
    this.isLoading = true;
    this.assets = [];
    const queriesString = buildQueriesFromFilters(this.filters).join(' AND ');
    const orderingString = this.getOrderQuery();

    if (this.ongoingFetch) {
      this.ongoingFetch.abort();
    }
    this.ongoingFetch = $.ajax({
      dataType: 'json',
      method: 'GET',
      url:
        `${ROOT_URL}/api/v2/project-views/${this.viewUid}/assets/?ordering=${orderingString}&limit=${PAGE_SIZE}` +
        (queriesString ? `&q=${queriesString}` : ''),
    })
      .done(this.onFetchAssetsDone.bind(this))
      .fail(this.onAnyFail.bind(this));
  }

  /** Gets the next page of results (if available). */
  public fetchMoreAssets() {
    if (this.nextPageUrl !== null) {
      if (this.ongoingFetch) {
        this.ongoingFetch.abort();
      }
      this.ongoingFetch = $.ajax({
        dataType: 'json',
        method: 'GET',
        url: this.nextPageUrl,
      })
        .done(this.onFetchMoreAssetsDone.bind(this))
        .fail(this.onAnyFail.bind(this));
    }
  }

  private onFetchAssetsDone(response: PaginatedResponse<ProjectViewAsset>) {
    this.isFirstLoadComplete = true;
    this.isLoading = false;
    this.assets = response.results;
    this.nextPageUrl = response.next;
  }

  private onFetchMoreAssetsDone(response: PaginatedResponse<ProjectViewAsset>) {
    // This differs from `onFetchAssetsDone`, because it adds the Assets
    // to existing ones.
    this.isLoading = false;
    this.assets = this.assets.concat(response.results);
    this.nextPageUrl = response.next;
  }

  private onAnyFail(response: FailResponse) {
    this.isLoading = false;
    handleApiFail(response);
  }

  /**
   * Stores settings for current view in `/me/` endpoint, so user will not lose
   * the configuration of the view after leaving the route.
   */
  private saveSettings() {
    // HACKFIX
    // TEMPORARILY DISABLES SAVING
    // If any of the fields is set to be required and given user will not have
    // it filled in - settings saving will not work, because this data is being
    // currently stored in `/me` endpoint. Working on a fix right now!
    const isAnyFieldRequired = envStore.data.user_metadata_fields.some(
      (field: EnvStoreFieldItem) => field.required
    );
    if (isAnyFieldRequired) {
      return;
    }
    // ENDHACKFIX

    if (!this.viewUid) {
      return;
    }

    let newData: ProjectViewsSettings = {};
    // Get saved data
    if (
      'email' in session.currentAccount &&
      session.currentAccount.extra_details.project_views_settings
    ) {
      newData = session.currentAccount.extra_details.project_views_settings;
    }

    newData[this.viewUid] = {
      filters: this.filters,
      order: this.order,
      fields: this.fields,
    };

    session.setDetail(SAVE_DATA_NAME, newData);
  }

  private resetSettings() {
    this.filters = DEFAULT_VIEW_SETTINGS.filters;
    this.order = DEFAULT_VIEW_SETTINGS.order;
    this.fields = DEFAULT_VIEW_SETTINGS.fields;
  }

  /**
   * Gets the settings for current view from session store (if they exists) with
   * fall back to defaults.
   */
  private loadSettings() {
    if (!this.viewUid) {
      return;
    }

    // First we load the default values
    this.resetSettings();

    // Then we load the saved settings (if they exist)
    if (
      'email' in session.currentAccount &&
      session.currentAccount.extra_details[SAVE_DATA_NAME] &&
      session.currentAccount.extra_details[SAVE_DATA_NAME][this.viewUid]
    ) {
      const savedViewData =
        session.currentAccount.extra_details[SAVE_DATA_NAME][this.viewUid];
      if (savedViewData.filters) {
        this.filters = savedViewData.filters;
      }
      if (savedViewData.order) {
        this.order = savedViewData.order;
      }
      if (savedViewData.fields) {
        this.fields = savedViewData.fields;
      }
    }
  }
}

/** Handles fetching (with filters and ordering) assets for given view. */
const customViewStore = new CustomViewStore();

export default customViewStore;
