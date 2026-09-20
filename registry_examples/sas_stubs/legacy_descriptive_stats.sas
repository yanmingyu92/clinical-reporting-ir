/********************************************************************************
 * legacy_descriptive_stats.sas — SYNTHETIC STUB for public release
 *
 * Mimics the *structure* of a legacy continuous-summary report macro
 * (parameter list, ODS RTF destination, output dataset) without containing
 * any production logic. Paired with the PUB-DEMOGRAPHICS entry in
 * registry_examples/bridge_map_sample.yaml.
 *
 * The parity harness's LegacyDriver invokes this macro through the bridge
 * map and captures the RTF written to &output_fileref.
 ********************************************************************************/

%macro legacy_descriptive_stats(
    population_from  = ,          /* input population dataset            */
    population_where = ,          /* subsetting WHERE clause             */
    analysis_var     = ,          /* continuous variable to summarize    */
    group_var        = ,          /* row grouping variable (optional)    */
    therapy_cd_var   = TRTCD,     /* treatment code variable             */
    therapy_des_var  = TRTDES,    /* treatment description variable      */
    decimal_places   = 1,         /* decimals for mean/SD display        */
    output_fileref   = fptotb,    /* fileref for the RTF destination     */
    output_data      = work._stats_out, /* summary statistics dataset    */
    title_text_1     = ,
    subtitle         = ,
    end_notes        = ,
    data_source_txt  = ,
    debug            = N
);

    %local nobs;

    /* --- compute summary statistics into an output dataset --------------- */
    proc means data=&population_from. n mean std median min max
               noprint;
        %if %length(&population_where.) > 0 %then
            where &population_where.;;
        var &analysis_var.;
        class &therapy_cd_var.;
        %if %length(&group_var.) > 0 %then class &group_var.;;
        output out=&output_data. n=_n mean=_mean std=_std
               median=_median min=_min max=_max;
    run;

    /* --- render to the ODS RTF destination -------------------------------- */
    ods rtf file=&output_fileref.;
    title1 "&title_text_1.";
    title2 "&subtitle.";
    footnote1 "&end_notes.";
    footnote2 "&data_source_txt.";

    proc report data=&output_data. nowd;
        column &therapy_cd_var. _n _mean _std _median _min _max;
        define _n      / "n";
        define _mean   / "Mean";
        define _std    / "SD";
        define _median / "Median";
        define _min    / "Min";
        define _max    / "Max";
    run;

    ods rtf close;

    %if %upcase(&debug.) = Y %then %do;
        proc print data=&output_data.; run;
    %end;

%mend legacy_descriptive_stats;
